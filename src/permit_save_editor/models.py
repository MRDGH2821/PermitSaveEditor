"""Pydantic v2 models for the Potion Permit save file.

The game's save format is a single JSON document with ~70+ top-level fields,
all using camelCase keys. Many sub-structures follow Unity's "serialized
dictionary" pattern: a 6-field shape with parallel ``_keys`` / ``_values``
lists. This module mirrors the C# ``Objects/`` tree from the original repo,
collapsing trivially-similar types (e.g. all the lock-state dicts) onto a
single ``SerializedDict`` base so the model stays compact.

Only fields the **editor** needs are typed precisely (Color, NPC health, the
lock-state lists, etc.). Everything else uses ``Any`` to preserve round-trip
fidelity without dragging the game's full schema into our type system.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# ---------------------------------------------------------------------------
# Shared model config
# ---------------------------------------------------------------------------
#
# - `populate_by_name=True`  -> construct via snake_case OR camelCase alias
# - `alias_generator=to_camel` -> snake_case Python fields serialize as
#   camelCase JSON keys (the game's convention)
# - `extra="ignore"` -> unknown JSON fields are silently dropped on load;
#   the game occasionally adds new fields, and we don't want to break
#   loading when that happens
_BaseConfig = ConfigDict(
    populate_by_name=True,
    alias_generator=to_camel,
    extra="ignore",
    str_strip_whitespace=True,
)


class _Base(BaseModel):
    """Project-wide pydantic base: snake↔camel aliases, ignore extras."""

    model_config = _BaseConfig


# ---------------------------------------------------------------------------
# Primitive sub-models (used directly by GameSaveData)
# ---------------------------------------------------------------------------


class Color(_Base):
    """RGBA color stored as 0.0-1.0 floats (the game's native format)."""

    a: float = 1.0
    r: float = 1.0
    g: float = 1.0
    b: float = 1.0

    def to_qcolor(self) -> tuple[int, int, int, int]:
        """Return 0-255 ints in (R, G, B, A) order — for Qt widgets."""
        return (
            round(self.r * 255),
            round(self.g * 255),
            round(self.b * 255),
            round(self.a * 255),
        )

    @classmethod
    def from_qcolor(cls, r: int, g: int, b: int, a: int = 255) -> Color:
        """Build from 0-255 ints (e.g. a QColor)."""
        return cls(r=r / 255, g=g / 255, b=b / 255, a=a / 255)


class Position(_Base):
    """Integer 2D position (used by RoomEditorData)."""

    x: int = 0
    y: int = 0


class RoomEditorData(_Base):
    """One room-object placement in the house editor."""

    room_object_str: str = ""
    room_object_id: int = Field(0, alias="roomObjectID")
    direction: int = 0
    position: Position = Field(default_factory=Position)


class NpcHealthData(_Base):
    """Per-NPC health record — used by the Heal-All button.

    The C# code hard-codes NpcHP=10 in the heal operation, so we model the
    only four fields the editor cares about.
    """

    cure_delay_cnt: int = Field(0, alias="cureDelayCnt")
    is_cure: bool = Field(False, alias="isCure")
    is_sick: bool = Field(False, alias="isSick")
    npc_hp: int = Field(10, alias="npcHP")

    def heal(self) -> None:
        """Reset to healthy state (matches the original C# HealAll)."""
        self.cure_delay_cnt = 0
        self.is_cure = False
        self.is_sick = False
        self.npc_hp = 10


# ---------------------------------------------------------------------------
# Unity-style serialized dictionary (the lock-state pattern)
# ---------------------------------------------------------------------------


class SerializedDict(_Base):
    """The 6-field pattern Unity uses for serialized dictionaries.

    The actual key/value data lives in parallel ``_keys`` / ``_values`` lists.
    ``_keyValues`` is the joined form. The other three fields are editor
    metadata (expanded/collapsed in Unity inspector, reorderable list, and a
    back-reference to the source asset).

    The original C# code declares ~15 separate classes with this exact shape
    (ItemLockState, MapResourceState, FastTravelState, PotionLockState,
    RecipeLockState, ...). We collapse them onto this one model since they
    only differ in the *type* of ``_values``, and the editor treats them all
    the same: read ``_values`` as a list of bools and set them all to True.
    """

    reorderable_list: Any = None
    req_references: Any = None
    is_expanded: bool = Field(False, alias="isExpanded")
    key_values: list[Any] = Field(default_factory=list, alias="_keyValues")
    # `_keys` is ``list[str]`` for string-keyed dicts (lock states, recipes, …)
    # and ``list[int]`` for int-keyed dicts (capsuleDict, upgradeDataDict,
    # diseasePatternList). We use ``list[Any]`` so the same model accepts both
    # while still round-tripping the original types byte-for-byte.
    keys: list[Any] = Field(default_factory=list, alias="_keys")
    values: list[Any] = Field(default_factory=list, alias="_values")

    @property
    def all_enabled(self) -> bool:
        """True if every value is truthy (matches `DataManager.AllEnabled`)."""
        return all(self.values) if self.values else False

    def unlock_all(self) -> None:
        """Set every value to True (matches `Extensions.UnlockAll`)."""
        self.values = [True] * len(self.values)


# ---------------------------------------------------------------------------
# Top-level save model
# ---------------------------------------------------------------------------


class GameSaveData(_Base):
    """The full Potion Permit save document.

    Field ordering roughly matches the C# ``GameSaveData`` class. Optional
    defaults are deliberately loose (empty list / 0 / empty string) so we
    can construct a blank save for the "new game" case without needing a
    fixture file.
    """

    # --- Identity ---
    is_empty_data: bool = Field(False, alias="isEmptyData")
    character_name: str = "Logan"
    dog_name: str = "Noxe"
    gender: int = 0  # 0 = male, 1 = female
    hair_id: int = Field(0, alias="hairID")

    # --- Time / progress ---
    day_count: int = 0
    day_id: int = Field(0, alias="dayID")
    play_time: float = 0.0
    story_timeline_index: int = 0
    pet_dogie_fp: int = 0

    # --- Resources ---
    gold: int = 500
    wood: int = 0
    stone: int = 0
    reputation: int = 0

    # --- Reputation / trust ---
    can_gain_trust: bool = False
    trust_point: int = 0
    trust_penalty: int = 0

    # --- Levels ---
    badge_level: int = Field(0, alias="badgeLevel")
    disease_level: int = Field(0, alias="diseaseLevel")
    blacksmith_level: int = Field(0, alias="blacksmithLevel")
    carpenter_level: int = Field(0, alias="carpenterLevel")

    # --- Part-time counters ---
    part_time_police_station_count: int = 0
    part_time_post_office_count: int = 0
    part_time_church_count: int = 0

    # --- Colors (5 slots) ---
    skin_color: Color = Field(default_factory=Color, alias="skinColor")
    hair_color: Color = Field(default_factory=Color, alias="hairColor")
    eyes_color: Color = Field(default_factory=Color, alias="eyesColor")
    cloth_color: Color = Field(default_factory=Color, alias="clothColor")
    cape_color: Color = Field(default_factory=Color, alias="capeColor")

    # --- Lock-state lists (parallel unlock buttons in the GUI) ---
    skin_lock_state_list: list[bool] = Field(
        default_factory=list, alias="skinLockStateList"
    )
    hair_lock_state_list: list[bool] = Field(
        default_factory=list, alias="hairLockStateList"
    )
    eyes_lock_state_list: list[bool] = Field(
        default_factory=list, alias="eyesLockStateList"
    )
    cloth_lock_state_list: list[bool] = Field(
        default_factory=list, alias="clothLockStateList"
    )
    cape_lock_state_list: list[bool] = Field(
        default_factory=list, alias="capeLockStateList"
    )

    # --- Unity serialized dicts (each is the same 6-field shape) ---
    item_lock_state: SerializedDict = Field(
        default_factory=SerializedDict, alias="itemLockState"
    )
    map_resource_state: SerializedDict = Field(
        default_factory=SerializedDict, alias="mapResourceState"
    )
    fast_travel_state: SerializedDict = Field(
        default_factory=SerializedDict, alias="fastTravelState"
    )
    potion_lock_state: SerializedDict = Field(
        default_factory=SerializedDict, alias="potionLockState"
    )
    recipe_lock_state: SerializedDict = Field(
        default_factory=SerializedDict, alias="recipeLockState"
    )
    tutorial_flag: SerializedDict = Field(
        default_factory=SerializedDict, alias="tutorialFlag"
    )
    trigger_disease_dict: SerializedDict = Field(
        default_factory=SerializedDict, alias="triggerDiseaseDict"
    )
    disease_pattern_list: SerializedDict = Field(
        default_factory=SerializedDict, alias="diseasePatternList"
    )
    capsule_dict: SerializedDict = Field(
        default_factory=SerializedDict, alias="capsuleDict"
    )
    upgrade_data_dict: SerializedDict = Field(
        default_factory=SerializedDict, alias="upgradeDataDict"
    )
    resources_records: SerializedDict = Field(
        default_factory=SerializedDict, alias="resourcesRecords"
    )
    achievement_dict: SerializedDict = Field(
        default_factory=SerializedDict, alias="achievementDict"
    )
    fish_exp_dict: SerializedDict = Field(
        default_factory=SerializedDict, alias="fishExpDict"
    )

    # --- Quest / progress ---
    is_first_disease: bool = Field(False, alias="isFirstDisease")
    target_quest_id: int = Field(0, alias="targetQuestID")
    target_quest: Any = None
    disease_day: int = 0
    disease_day_counter_sudden: int = 0
    disease_counter: int = 0

    # --- Heterogeneous lists — typed loosely to survive schema changes ---
    player_inventory_item_data: list[Any] = Field(
        default_factory=list, alias="playerInventoryItemData"
    )
    player_vending_data: list[Any] = Field(
        default_factory=list, alias="playerVendingData"
    )
    potion_save_data: list[Any] = Field(default_factory=list, alias="potionSaveData")
    key_item_active_list: list[Any] = Field(
        default_factory=list, alias="keyItemActiveList"
    )
    research_list: list[str] = Field(default_factory=list, alias="researchList")
    new_material_list: list[str] = Field(
        default_factory=list, alias="newMaterialList"
    )
    new_food_id_list: list[str] = Field(
        default_factory=list, alias="newFoodIDList"
    )
    new_potion_id_list: list[Any] = Field(
        default_factory=list, alias="newPotionIDList"
    )
    new_fish_id_list: list[Any] = Field(
        default_factory=list, alias="newFishIDList"
    )
    new_npc_id_list: list[str] = Field(default_factory=list, alias="newNpcIDList")
    new_enemy_id_list: list[str] = Field(
        default_factory=list, alias="newEnemyIDList"
    )
    new_tutorial_id_list: list[str] = Field(
        default_factory=list, alias="newTutorialIDList"
    )
    new_disease_data_list: list[Any] = Field(
        default_factory=list, alias="newDiseaseDataList"
    )
    new_quest_data_list: list[str] = Field(
        default_factory=list, alias="newQuestDataList"
    )
    event_state_data: list[Any] = Field(default_factory=list, alias="eventStateData")
    active_quest_list: list[Any] = Field(
        default_factory=list, alias="activeQuestList"
    )
    queue_quest_list: list[Any] = Field(
        default_factory=list, alias="queueQuestList"
    )
    quest_progress_list: list[Any] = Field(
        default_factory=list, alias="questProgressList"
    )
    npc_fp_data_list: list[Any] = Field(
        default_factory=list, alias="npcFPDataList"
    )
    npc_health_data_list: list[NpcHealthData] = Field(
        default_factory=list, alias="npcHealthDataList"
    )
    room_editor_data: list[RoomEditorData] = Field(
        default_factory=list, alias="roomEditorData"
    )
    active_disease_list: list[Any] = Field(
        default_factory=list, alias="activeDiseaseList"
    )
    progression_obj_data_list: list[Any] = Field(
        default_factory=list, alias="progressionObjDataList"
    )
    status_upgrade_list: list[Any] = Field(
        default_factory=list, alias="statusUpgradeList"
    )
    enemy_slain_datas: list[Any] = Field(
        default_factory=list, alias="enemySlainDatas"
    )
    enemy_quest_datas: list[Any] = Field(
        default_factory=list, alias="enemyQuestDatas"
    )
    fish_record_list: list[Any] = Field(
        default_factory=list, alias="fishRecordList"
    )
    camp_bed_list: list[Any] = Field(default_factory=list, alias="campBedList")

    # -- The big operations the editor performs -----------------------------

    def unlock_everything(self) -> None:
        """Bulk-unlock every category the WPF editor had a button for.

        Mirrors the eight `*_Unlock_Click` handlers in MainWindow.xaml.cs and
        the C# ``Extensions.UnlockAll`` helper.
        """
        for lock_list in (
            self.skin_lock_state_list,
            self.hair_lock_state_list,
            self.eyes_lock_state_list,
            self.cloth_lock_state_list,
            self.cape_lock_state_list,
        ):
            for i in range(len(lock_list)):
                lock_list[i] = True

        self.fast_travel_state.unlock_all()
        self.recipe_lock_state.unlock_all()
        self.potion_lock_state.unlock_all()

    def heal_all_npcs(self) -> None:
        """Reset every NPC to healthy (mirrors C# ``Extensions.HealAll``)."""
        for npc in self.npc_health_data_list:
            npc.heal()


__all__ = [
    "Color",
    "GameSaveData",
    "NpcHealthData",
    "Position",
    "RoomEditorData",
    "SerializedDict",
]
