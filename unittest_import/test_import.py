#! /usr/bin/python
import curses

import pprint
import traceback
import unittest

import ca_debug
import ca_gcs_import
import diff_json

from unittest_main.test_common import GmTestCaseCommon

class GmTestCaseImport(GmTestCaseCommon):
    debug = ca_debug.Debug()
    good_data = {
        'unittest_import/Char1.gcs': {
              "actions_this_turn": [],
              "armor-index": [],
              "current": {
                "fp": 9, "iq": 13, "hp": 10, "wi": 13,
                "st": 8, "ht": 9, "dx": 15,
                "basic-move": 6, "basic-speed": 6.0, "per": 13
              },
              "current-weapon": 0, "fight-notes": [],
              "ignored-equipment": [], "notes": [],
              "open-container": [], "opponent": None,
              "permanent": {
                "fp": 9, "iq": 13, "hp": 10, "wi": 13,
                "st": 8, "ht": 9, "dx": 15,
                "basic-move": 6, "basic-speed": 6.0, "per": 13
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [
                { "name": "Antitoxin Kit",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "Antidote for specific poison. 10 uses",
                  "owners": None
                },
                {
                  "name": "Baseball cards",
                  "type": { "misc": {} },
                  "count": 8355,
                  "notes": "Value in $, equivalent to 10 eRubles",
                  "owners": None
                },
                {
                  "name": "Finger Bones",
                  "type": { "container": {} },
                  "count": 1, "notes": "", "owners": None,
                  "stuff": [
                    {
                      "name": "Fog finger bone (gray) ",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    {
                      "name": "Luck Finger Bone (yellow) ",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    {
                      "name": "Major Heal finger bone (green) ",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    }
                  ]
                },
                {
                  "name": "First Aid Kit",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "A complete kit for treating wounds, with bandages, ointments, etc.",
                  "owners": None,
                  "bonus": [{'amount': 1, 'name': 'First Aid', 'type': 'skill'}]

                },
                {
                  "name": "Large Knife",
                  "type": {
                    "swung weapon": {
                      "damage": { "st": "sw", "plus": -2, "type": "cut" },
                      "skill": {
                        "DX": -4, "Knife": 0, "Force Sword": -3, "Main-Gauche": -3,
                        "Shortsword": -3, "Sword!": 0 }
                    },
                    "thrust weapon": {
                      "damage": { "st": "thr", "plus": 0, "type": "imp" },
                      "skill": {
                        "DX": -4, "Knife": 0, "Force Sword": -3,
                        "Main-Gauche": -3, "Shortsword": -3, "Sword!": 0
                      }
                    },
                    "ranged weapon": {
                      "damage": { "st": "thr", "plus": 0, "type": "imp" },
                      "skill": { "DX": -4, "Thrown Weapon (Knife)": 0 }
                    }
                  },
                  "count": 4, "notes": "", "owners": None, "parry": -1,
                  "bulk": -2, "acc": 0,
                  "reload_type": 0
                },
                {
                  "name": "Leopard Print Armor",
                  "type": { "armor": { "dr": 4 } },
                  "count": 1, "notes": "", "owners": None
                },
                {
                  "name": "Lockpicks",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "Basic equipment for Lockpicking skill",
                  "owners": None
                },
                {
                  "name": "Poison",
                  "type": { "misc": {} },
                  "count": 20,
                  "notes": "2d HP damage, no delay, follow-up (on knife tip) poison",
                  "owners": None
                },
                {
                  "name": "Small Knife",
                  "type": {
                    "swung weapon": {
                      "damage": { "st": "sw", "plus": -3, "type": "cut" },
                      "skill": {
                        "DX": -4, "Knife": 0, "Force Sword": -3,
                        "Main-Gauche": -3, "Shortsword": -3, "Sword!": 0 }
                    },
                    "thrust weapon": {
                      "damage": { "st": "thr", "plus": -1, "type": "imp" },
                      "skill": {
                        "DX": -4, "Knife": 0, "Force Sword": -3,
                        "Main-Gauche": -3, "Shortsword": -3, "Sword!": 0 }
                    },
                    "ranged weapon": {
                      "damage": { "st": "thr", "plus": -1, "type": "imp" },
                      "skill": { "DX": -4, "Thrown Weapon (Knife)": 0 }
                    }
                  },
                  "count": 5, "notes": "", "owners": None, "parry": -1,
                  "bulk": -1, "acc": 0,
                  "reload_type": 0
                },
                {
                  "name": "Death Powder ",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                {
                  "name": "Laser Pistol",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": { "dice": { "num_dice": 2, "plus": 4, "type": "pi" } },
                      "skill": {}
                    }
                  },
                  "count": 1, "notes": "", "owners": None,
                  "bulk": -2, "acc": 4,
                  "reload_type": 2, "reload": 2,
                  "ammo": { "name": "** UNKNOWN **", "shots": 8, "shots_left": 8 }
                }
              ],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "Always snacking, always carrying food": -1,
                "Combat Reflexes": 15,
                "Debt": -10,
                "G-Experience": 3,
                "High Pain Threshold": 10,
                "Miserliness": -10,
                "Obsession": -1,
                "Overconfidence": -7,
                "Wealth": -10
              },
              "aim": { "braced": False, "rounds": 0 },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char1.gcs",
              "posture": "standing",
              "shock": 0,
              "skills": {
                "Urban Survival": 12,
                "Thrown Weapon (Knife)": 15,
                "Streetwise": 12,
                "Stealth": 16,
                "Smuggling": 13,
                "Shadowing": 12,
                "Search": 12,
                "Savoir-Faire (Police)": 13,
                "Savoir-Faire (Mafia)": 13,
                "Poisons": 13,
                "Pickpocket": 15,
                "Lockpicking": 13,
                "Knife": 17,
                "Holdout": 12,
                "Beam Weapons (Pistol)": 15,
                "Filch": 15,
                "Fast-Talk": 14,
                "Fast-Draw (Knife)": 16,
                "Escape": 13,
                "Electronics Operation (Sensors)": 13,
                "Electronics Operation (Security)": 13,
                "Connoisseur (Wine)": 12,
                "Climbing": 15,
                "Brawling": 15,
                "Biology (Biochemistry)": 10,
                "Area Knowledge (Persephone; Lived there)": 13,
                "Acrobatics": 13
              },
              "stunned": False,
              "techniques": [
                {
                  "name": "Off-Hand Weapon Training",
                  "default": "Knife",
                  "value": -3
                },
                {
                  "name": "Disarming",
                  "default": "Knife",
                  "value": 1
                }
              ],
              "spells": []
        },

        'unittest_import/Char2.gcs': {
              "actions_this_turn": [],
              "armor-index": [],
              "current": {
                "fp": 10, "iq": 14, "hp": 12, "wi": 14,
                "st": 10, "ht": 9, "dx": 13,
                "basic-move": 6, "basic-speed": 6.0, "per": 14
              },
              "current-weapon": 0, "fight-notes": [], "ignored-equipment": [],
              "notes": [], "open-container": [], "opponent": None,
              "permanent": {
                "fp": 10, "iq": 14, "hp": 12, "wi": 14,
                "st": 10, "ht": 9, "dx": 13,
                "basic-move": 6, "basic-speed": 6.0, "per": 14
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [
                { # 0
                  "name": "eRuble",
                  "type": { "misc": {} },
                  "count": 76500,
                  "notes": "",
                  "owners": None
                },
                { # 1
                  "name": "Hacking Equipment +1",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "",
                  "owners": None,
                  "bonus": [{'amount': 1, 'name': 'Computer Hacking', 'type': 'skill'}]
                },
                { # 2
                  "name": "Sick Stick",
                  "type": {
                    "swung weapon": {
                      "damage": {
                          "dice": { "num_dice": 1, "plus": 1, "type": "fat" }
                      },
                      "skill": {
                        "DX": -5, "Force Sword": -4, "Broadsword": 0,
                        "Rapier": -4, "Saber": -4, "Shortsword": -2,
                        "Two-Handed Sword": -4, "Axe/Mace": 0
                      }
                    }
                  },
                  "count": 1,
                  "notes": "On hit: make HT roll or vomit (out 1d/3 turns)",
                  "owners": None,
                  "parry": 0
                },
                { # 3
                  "name": "Laser Sight",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "+1 to skill; see Laser Sights (B412). 6 hrs.",
                  "owners": None,
                  "bonus": [{'amount': 1, 'name': 'Beam Weapons', 'type': 'skill'}]
                },
                { # 4
                  "name": "Voice Synthesizer",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 5
                  "name": "Holster, Belt",
                  "type": { "misc": {} },
                  "count": 1, "notes": "For pistols.", "owners": None
                },
                { # 6
                  "name": "Blaster Pistol, Colt Series 170D",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": {
                        "dice": { "num_dice": 1, "plus": 4, "type": "HP" }
                      },
                      "skill": {
                        "DX": -4, "Beam Weapons (Pistol)": 0,
                        "Beam Weapons": -4, "Guns (Pistol)": -4
                      }
                    }
                  },
                  "count": 1, "notes": "C/9 shots", "owners": None,
                  "bulk": -2, "acc": 3,
                  "reload_type": 2, "reload": 2,
                  "ammo": { "name": "** UNKNOWN **", "shots": 9, "shots_left": 9 }
                },
                { # 7
                  "name": "Armor Support Garment",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { #8
                  "name": "Ballistic DR5",
                  "type": { "armor": { "dr": 5 } },
                  "count": 1, "notes": "", "owners": None
                },
                { # 9
                  "name": "Ablative DR5",
                  "type": { "armor": { "dr": 0 } },
                  "count": 1, "notes": "", "owners": None
                },
                { # 10
                  "name": "Camera",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 11
                  "name": "Backpack, Small",
                  "type": { "container": {} },
                  "count": 1, "notes": "", "owners": None,
                  "stuff": [
                    { # 0
                      "name": "Duct Tape",
                      "type": {
                        "ranged weapon": {
                          "damage": { "st": "sw", "plus": 2, "type": "cr" },
                          "skill": { "DX": -4, "Thrown Weapon (Axe/Mace)": 0 }
                        }
                      },
                      "count": 1,
                      "notes": "60 yard roll. ST-3 or Escape roll to break free.",
                      "owners": None, "bulk": -3, "acc": 1,
                      "reload_type": 0
                    },
                    { # 1
                      "name": "First Aid Kit",
                      "type": { "misc": {} },
                      "count": 1,
                      "notes": "A complete kit for treating wounds, with bandages, ointments, etc.",
                      "owners": None,
                      "bonus": [{'amount': 1, 'name': 'First Aid', 'type': 'skill'}]
                    },
                    { # 2
                      "name": "Multi-Tool with Flashlight",
                      "type": { "misc": {} },
                      "count": 1, "notes": "Most repairs -5.", "owners": None
                    },
                    { # 3
                      "name": "Spare Batteries",
                      "type": { "misc": {} },
                      "count": 4, "notes": "", "owners": None
                    },
                    { # 4
                      "name": "Battery 3/10",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 5
                      "name": "Heavy Heal Patch",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    }
                  ]
                }
              ],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "Cannot Speak (Mute) - Computer Voice Synthesizer": -10,
                "Humble": -1,
                "Secret (Turned in evidence on brutal mob hit)": -30,
                "Squeamish": -10,
                "Eidetic Memory": 5,
                "Acute Vision": 2,
                "G-Experience": 1,
                "Fit": 5
              },
              "aim": { "braced": False, "rounds": 0 },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char2.gcs",
              "posture": "standing",
              "shock": 0,
              "skills": {
                "Brawling": 13,
                "Beam Weapons (Pistol)": 16,
                "Beam Weapons (Rifle)": 20,
                "Axe/Mace": 13,
                "Law (Conglomerate, trans-territorial jurisdiction/the void)": 12,
                "Cryptography": 13,
                "Electronics Operation (Security)": 14,
                "Expert Skill (Computer Security)": 13,
                "Computer Programming": 13,
                "Piloting (Low-Performance Spacecraft)": 20,
                "Piloting (Loader Mech)": 16,
                "Engineer (Electronics)": 13,
                "Engineer (Starships)": 13,
                "Computer Hacking": 18,
                "Mathematics (Applied)": 12,
                "Physics": 12,
                "Armoury (Small Arms)": 14,
                "Climbing": 13,
                "Forensics": 14,
                "Search": 14,
                "Lip Reading": 13,
                "Fast-Draw (Ammo)": 15
              },
              "stunned": False, "techniques": [], "spells": []
        },

        'unittest_import/Char3.gcs': {
              "actions_this_turn": [], "armor-index": [],
              "current": {
                "fp": 13, "iq": 15, "hp": 10, "wi": 15,
                "st": 9, "ht": 11, "dx": 9,
                "basic-move": 5, "basic-speed": 5, "per": 15
              },
              "current-weapon": 0, "fight-notes": [],
              "ignored-equipment": [], "notes": [],
              "open-container": [], "opponent": None,
              "permanent": {
                "fp": 13, "iq": 15, "hp": 10, "wi": 15,
                "st": 9, "ht": 11, "dx": 9,
                "basic-move": 5, "basic-speed": 5, "per": 15
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [
                { # 0
                  "name": "Backpack, Small",
                  "type": { "container": {} },
                  "count": 1, "notes": "", "owners": None,
                  "stuff": [
                    { # 0
                      "name": "Alpaca hat",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 1
                      "name": "Alpaca lapel pin",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 2
                      "name": "Alpaca socks",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 3
                      "name": "Alpaca T-Shirt",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 4
                      "name": "Alpaca wool",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 5
                      "name": "Cigarette Lighter",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 6
                      "name": "Drop Spindle",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 7
                      "name": "Duct Tape",
                      "type": {
                        "ranged weapon": {
                          "damage": { "st": "sw", "plus": 2, "type": "cr" },
                          "skill": { "dx": -4, "Thrown Weapon (Axe/Mace)": 0 }
                        }
                      },
                      "count": 1,
                      "notes": "60 yard roll. ST-3 or Escape roll to break free.",
                      "owners": None, "bulk": -3, "acc": 1,
                      "reload_type": 0
                    },
                    { # 8
                      "name": "Flashlight, Heavy",
                      "type": { "misc": {} },
                      "count": 1, "notes": "30' beam, lasts 5 hours",
                      "owners": None
                    },
                    { # 9
                      "name": "Keys",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 10
                      "name": "Knitting Needles, Pair",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 11
                      "name": "Sheep Skin Alpaca",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 12
                      "name": "Sunglasses",
                      "type": { "armor": { "dr": 1 } },
                      "count": 1,
                      "notes": "Protected Vision vs. ordinary light.",
                      "owners": None
                    },
                    { # 13
                      "name": "Weed",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 14
                      "name": "Whistle",
                      "type": { "armor": { "dr": 4 }
                      },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 15
                      "name": "Wooden Alpaca Figure",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 16
                      "name": "Wool",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 17
                      "name": "Yarn Alpaca",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    }
                  ]
                },
                { # 1
                  "name": "Blaster Pistol, Sig Sauer D65",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": {
                        "dice": { "num_dice": 1, "plus": 4, "type": "fat" }
                      },
                      "skill": {
                        "dx": -4, "Beam Weapons (Pistol)": 0,
                        "Beam Weapons": -4, "Guns (Pistol)": -4
                      }
                    }
                  },
                  "count": 1, "notes": "C/9 shots", "owners": None,
                  "bulk": -2, "acc": 4,
                  "reload_type": 2, "reload": 3,
                  "ammo": { "name": "** UNKNOWN **", "shots": 9, "shots_left": 9 }
                },
                { # 2
                  "name": "Armor",
                  "type": { "armor": { "dr": 5 } },
                  "count": 1, "notes": "", "owners": None
                },
                { # 3
                  "name": "Camera",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 4
                  "name": "Large Knife",
                  "type": {
                    "swung weapon": {
                      "damage": { "st": "sw", "plus": -2, "type": "cut" },
                      "skill": {
                        "dx": -4, "Knife": 0,
                        "Force Sword": -3, "Main-Gauche": -3,
                        "Shortsword": -3, "Sword!": 0
                      }
                    },
                    "thrust weapon": {
                      "damage": { "st": "thr", "plus": 0, "type": "imp" },
                      "skill": {
                        "dx": -4, "Knife": 0,
                        "Force Sword": -3, "Main-Gauche": -3,
                        "Shortsword": -3, "Sword!": 0
                      }
                    },
                    "ranged weapon": {
                      "damage": { "st": "thr", "plus": 0, "type": "imp" },
                      "skill": {
                        "dx": -4, "Thrown Weapon (Knife)": 0
                      }
                    }
                  },
                  "count": 1, "notes": "", "owners": None,
                  "parry": -1, "bulk": -2, "acc": 0,
                  "reload_type": 0
                },
                { # 5
                  "name": "Sick Stick",
                  "type": {
                    "swung weapon": {
                      "damage": {
                        "dice": { "num_dice": 1, "plus": 1, "type": "fat" }
                      },
                      "skill": {
                        "dx": -5, "Force Sword": -4,
                        "Broadsword": 0, "Rapier": -4,
                        "Saber": -4, "Shortsword": -2,
                        "Two-Handed Sword": -4, "Axe/Mace": 0
                      }
                    }
                  },
                  "count": 1,
                  "notes": "On hit: make HT roll or vomit (out 1d/3 turns)",
                  "owners": None,
                  "parry": 0
                },
                { # 6
                  "name": "Small Knife",
                  "type": {
                    "swung weapon": {
                      "damage": { "st": "sw", "plus": -3, "type": "cut" },
                      "skill": {
                        "dx": -4, "Knife": 0,
                        "Force Sword": -3, "Main-Gauche": -3,
                        "Shortsword": -3, "Sword!": 0
                      }
                    },
                    "thrust weapon": {
                      "damage": { "st": "thr", "plus": -1, "type": "imp" },
                      "skill": {
                        "dx": -4, "Knife": 0,
                        "Force Sword": -3, "Main-Gauche": -3,
                        "Shortsword": -3, "Sword!": 0
                      }
                    },
                    "ranged weapon": {
                      "damage": { "st": "thr", "plus": -1, "type": "imp" },
                      "skill": { "dx": -4, "Thrown Weapon (Knife)": 0 } }
                  },
                  "count": 1, "notes": "", "owners": None,
                  "parry": -1, "bulk": -1, "acc": 0,
                  "reload_type": 0
                },
                { # 7
                  "name": "Wristwatch",
                  "type": { "armor": { "dr": 4 } },
                  "count": 1, "notes": "", "owners": None
                },
                { # 8
                  "name": "Flash drive with logs from tereshkova",
                  "type": { "misc": {} },
                  "count": 2, "notes": "", "owners": None
                },
                { # 9
                  "name": "major heal finger bone",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 10
                  "name": "shrunken head stick",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 11
                  "name": "pretty beaded necklaces",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                }
              ],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "Advantage": 0,
                "Alcohol Intolerance": -1,
                "Bad Temper": -10,
                "Combat Reflexes": 15,
                "Cultural Familiarity (Teraformers)": 1,
                "Curious": -7,
                "Deep Sleeper": 1,
                "Dreamer": -1,
                "Empathy": 15,
                "Extra Hit Points": 2,
                "G-Experience": 1,
                "Habit": -1,
                "Honest Face": 1,
                "Impulsiveness": -15,
                "Like knick knacks": -1,
                "Lwa (Bokor)": 6,
                "Nosy": -1,
                "Short Attention Span": -15,
                "Versatile": 5,
                "Wealth": -10,
                "Vodou Practitioner": 45
              },
              "aim": { "braced": False, "rounds": 0 },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char3.gcs",
              "posture": "standing", "shock": 0,
              "skills": {
                "Area Knowledge (Space Station)": 17,
                "Axe/Mace/Sick Stick": 8,
                "Beam Weapons (Pistol)": 12,
                "Brawling": 11,
                "Climbing": 8,
                "Computer Hacking": 14,
                "Computer Operation": 15,
                "Computer Programming": 13,
                "Current Affairs (Teraforming)": 15,
                "Detect Lies": 17,
                "Diplomacy": 15,
                "Electronics Operation (Security)": 15,
                "Electronics Repair (Security)": 16,
                "Electronics Repair (Teraforming)": 14,
                "Escape": 9,
                "Fast-Talk": 16,
                "Knife": 10,
                "Law (Conglomorate, trans-territorial/the void)": 14,
                "Lip Reading": 15,
                "Mechanic (Spacecraft)": 16,
                "Piloting (Low-Performance Spacecraft)": 8,
                "Streetwise": 16
              },
              "stunned": False, "techniques": [],
              "spells": [
                { "name": "Boost Dexterity", "skill": 14 },
                { "name": "Bravery", "skill": 13 },
                { "name": "Clumsiness", "skill": 14 },
                { "name": "Daze", "skill": 13 },
                { "name": "Emotion Control", "skill": 13 },
                { "name": "Fear", "skill": 13 },
                { "name": "Foolishness", "skill": 13 },
                { "name": "Fumble", "skill": 14 },
                { "name": "Grace", "skill": 14 },
                { "name": "Itch", "skill": 14 },
                { "name": "Loyalty", "skill": 13 },
                { "name": "Luck", "skill": 15 },
                { "name": "Mass Sleep", "skill": 14 },
                { "name": "Pain", "skill": 13 },
                { "name": "Panic", "skill": 14 },
                { "name": "Sense Emotion", "skill": 14 },
                { "name": "Sense Foes", "skill": 14 },
                { "name": "Sensitize", "skill": 15 },
                { "name": "Shapeshifting (rat)", "skill": 14 },
                { "name": "Sleep", "skill": 14 },
                { "name": "Spasm", "skill": 14 },
                { "name": "Stun", "skill": 15 },
                { "name": "Truthsayer", "skill": 14 }
              ]
        },

        'unittest_import/Char4.gcs': {
              "actions_this_turn": [], "armor-index": [],
              "current": {
                "fp": 8, "iq": 17, "hp": 11, "wi": 17,
                "st": 9, "ht": 8, "dx": 9,
                "basic-move": 4, "basic-speed": 4.25, "per": 17
              },
              "current-weapon": 0, "fight-notes": [],
              "ignored-equipment": [], "notes": [],
              "open-container": [], "opponent": None,
              "permanent": {
                "fp": 8, "iq": 17, "hp": 11, "wi": 17,
                "st": 9, "ht": 8, "dx": 9,
                "basic-move": 4, "basic-speed": 4.25, "per": 17
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [
                { # 0
                  "name": "Pump Shotgun, 12G",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": {
                        "dice": {
                          "num_dice": 1,
                          "plus": 1,
                          "type": "pi"
                        }
                      },
                      "skill": {
                        "Guns (Shotgun)": 0,
                        "dx": -4,
                        "Guns (Light Machine Gun)": -2,
                        "Guns (Musket)": -2,
                        "Guns (Pistol)": -2,
                        "Guns (Rifle)": -2,
                        "Guns (Submachine Gun)": -2,
                        "Guns (Grenade Launcher)": -4,
                        "Guns (Gyroc)": -4,
                        "Guns (Light Anti-Armor Weapon)": -4
                      }
                    }
                  },
                  "count": 1, "notes": "", "owners": None,
                  "bulk": -5, "acc": 3,
                  "ammo": { "name": "** UNKNOWN **", "shots": 7, "shots_left": 7 },
                  "reload_type": 1, "reload": 2
                }
              ],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "Cowardice": -10,
                "Compulsive Carousing": -5,
                "Greed": -15,
                "Slow Eater": -10,
                "Natural Attacks": 0,
                "Charisma": 5,
                "Eidetic Memory": 10,
                "Empathy": 23,
                "Enhanced Dodge": 15,
                "Extra Hit Points": 2,
                "Fashion Sense": 5,
                "Luck": 15,
                "Social Chameleon": 5,
                "Unfazeable": 15
              },
              "aim": { "braced": False, "rounds": 0 },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char4.gcs",
              "posture": "standing",
              "shock": 0,
              "skills": {
                "Carousing": 8,
                "Detect Lies": 18,
                "Diplomacy": 15,
                "Fast-Talk": 16,
                "Finance": 15,
                "Forgery": 15,
                "Gesture": 17,
                "Guns (Pistol)": 12,
                "Holdout": 16,
                "Interrogation": 16,
                "Leadership": 17,
                "Lip Reading": 16,
                "Persuade": 15,
                "Politics": 16,
                "Public Speaking": 17,
                "Savoir-Faire (Bureaucracy)": 17,
                "Smuggling": 16,
                "Streetwise": 16,
                "Throwing": 8
              },
              "stunned": False, "techniques": [], "spells": []
        },

        'unittest_import/Char5.gcs': {
              "actions_this_turn": [], "armor-index": [],
              "current": {
                "fp": 11, "iq": 12, "hp": 12, "wi": 12,
                "st": 10, "ht": 11, "dx": 15,
                "basic-move": 6, "basic-speed": 6.5, "per": 13
              },
              "current-weapon": 0, "fight-notes": [],
              "ignored-equipment": [], "notes": [],
              "open-container": [], "opponent": None,
              "permanent": {
                "fp": 11, "iq": 12, "hp": 12, "wi": 12,
                "st": 10, "ht": 11, "dx": 15,
                "basic-move": 6, "basic-speed": 6.5, "per": 13
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [
                { # 0
                  "name": "Ablative & Ballistic Armor",
                  "type": { "armor": { "dr": 5 } },
                  "count": 1,
                  "notes": "Support Garment with ablative & Ballistic properties",
                  "owners": None
                },
                { # 1
                  "name": "Wicking Undergarment",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 2
                  "name": "Ballistic Gloves",
                  "type": { "armor": { "dr": 16 } },
                  "count": 1, "notes": "", "owners": None
                },
                { # 3
                  "name": "Holster, Shoulder",
                  "type": { "container": {} },
                  "count": 1,
                  "notes": "Allows use of Holdout, but gives -1 to Fast-Draw.",
                  "owners": None,
                  "stuff": [
                    { # 0
                      "name": "Lanyard, Woven Steel",
                      "type": { "container": {} },
                      "count": 1,
                      "notes": "Lets you retrieve a dropped weapon on a DX roll. Each attempt requires a Ready maneuver. Can be cut: -6 to hit, DR 6, HP 4.",
                      "owners": None,
                      "stuff": [
                        { # 0
                          "name": "Blaster Pistol, Sig Sauer D65",
                          "stuff": [],
                          "type": {
                              "container": 1,
                            "ranged weapon": {
                              "damage": {
                                "dice": {
                                  "num_dice": 1,
                                  "plus": 4,
                                  "type": "fat"
                                }
                              },
                              "skill": {
                                "dx": -4,
                                "Beam Weapons (Pistol)": 0,
                                "Beam Weapons": -4,
                                "Guns (Pistol)": -4
                              }
                            }
                          },
                          "count": 1, "notes": "9/9", "owners": None,
                          "bulk": -2, "acc": 4,
                          "reload_type": 2, "reload": 3,
                          "ammo": {
                            "name": "** UNKNOWN **",
                            "shots": 9,
                            "shots_left": 9
                          }
                        },
                        { # 1
                          "name": "Targeting Laser (Sidearm)",
                          "type": { "misc": {} },
                          "count": 1,
                          "notes": "150-yard range. 2xXS/50hrs.",
                          "owners": None,
                          "bonus": [{'amount': 1, 'name': 'Beam Weapons', 'type': 'skill'}]
                        }
                      ]
                    }
                  ]
                },
                { # 4
                  "name": "Holster, Shoulder",
                  "type": { "container": {} },
                  "count": 1,
                  "notes": "Allows use of Holdout, but gives -1 to Fast-Draw.",
                  "owners": None,
                  "stuff": [
                    {
                      "name": "Lanyard, Woven Steel",
                      "type": { "container": {} },
                      "count": 1,
                      "notes": "Lets you retrieve a dropped weapon on a DX roll. Each attempt requires a Ready maneuver. Can be cut: -6 to hit, DR 6, HP 4.",
                      "owners": None,
                      "stuff": [
                        {
                          "name": "Blaster Pistol, Baretta DX 192",
                          "stuff": [],
                          "type": {
                            "container": 1,
                            "ranged weapon": {
                              "damage": {
                                "dice": {
                                  "num_dice": 1,
                                  "plus": 4,
                                  "type": "fat"
                                }
                              },
                              "skill": {
                                "dx": -4,
                                "Beam Weapons (Pistol)": 0,
                                "Beam Weapons": -4,
                                "Guns (Pistol)": -4
                              }
                            }
                          },
                          "count": 1, "notes": "8/8 shots",
                          "owners": None, "bulk": -2, "acc": 2,
                          "reload_type": 2, "reload": 3,
                          "ammo": {
                            "name": "** UNKNOWN **",
                            "shots": 8,
                            "shots_left": 8
                          }
                        },
                        {
                          "name": "Targeting Laser (Sidearm)",
                          "type": { "misc": {} },
                          "count": 1,
                          "notes": "150-yard range. 2xXS/50hrs.",
                          "owners": None
                        }
                      ]
                    }
                  ]
                },
                { # 5
                  "name": "Web Gear",
                  "type": { "container": {} },
                  "count": 1,
                  "notes": "Belt and suspenders with puches and rings for gear",
                  "owners": None,
                  "stuff": [
                    {
                      "name": "Sheath",
                      "type": { "container": {} },
                      "count": 1,
                      "notes": "",
                      "owners": None,
                      "stuff": [
                        {
                          "name": "Large Knife",
                          "type": {
                            "swung weapon": {
                              "damage": {
                                "st": "sw",
                                "plus": -2,
                                "type": "cut"
                              },
                              "skill": {
                                "dx": -4,
                                "Knife": 0,
                                "Force Sword": -3,
                                "Main-Gauche": -3,
                                "Shortsword": -3,
                                "Sword!": 0
                              }
                            },
                            "thrust weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": 0,
                                "type": "imp"
                              },
                              "skill": {
                                "dx": -4,
                                "Knife": 0,
                                "Force Sword": -3,
                                "Main-Gauche": -3,
                                "Shortsword": -3,
                                "Sword!": 0
                              }
                            },
                            "ranged weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": 0,
                                "type": "imp"
                              },
                              "skill": {
                                "dx": -4,
                                "Thrown Weapon (Knife)": 0
                              }
                            }
                          },
                          "count": 1, "notes": "", "owners": None,
                          "parry": -1, "bulk": -2, "acc": 0,
                          "reload_type": 0
                        }
                      ]
                    },
                    {
                      "name": "Sheath",
                      "type": { "container": {} },
                      "count": 1,
                      "notes": "Fits most pistols",
                      "owners": None,
                      "stuff": [
                        {
                          "name": "Machete",
                          "type": {
                            "swung weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": -1,
                                "type": "imp"
                              },
                              "skill": {
                                "dx": -4,
                                "Knife": 0,
                                "Force Sword": -3,
                                "Main-Gauche": -3,
                                "Shortsword": -3
                              }
                            }
                          },
                          "count": 1, "notes": "", "owners": None, "parry": 0
                        }
                      ]
                    },
                    {
                      "name": "Sick Stick",
                      "type": {
                        "swung weapon": {
                          "damage": {
                            "dice": {
                              "num_dice": 1,
                              "plus": 1,
                              "type": "fat"
                            }
                          },
                          "skill": {
                            "dx": -5,
                            "Force Sword": -4,
                            "Broadsword": 0,
                            "Rapier": -4,
                            "Saber": -4,
                            "Shortsword": -2,
                            "Two-Handed Sword": -4,
                            "Axe/Mace": 0
                          }
                        }
                      },
                      "count": 1,
                      "notes": "On hit: make HT roll or vomit (out 1d/3 turns)",
                      "owners": None,
                      "parry": 0
                    },
                    {
                      "name": "Pocket Watch",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    {
                      "name": "Electronic Cuffs",
                      "type": { "misc": {} },
                      "count": 1,
                      "notes": "ST 20. DR 10. A/1wk.",
                      "owners": None
                    },
                    {
                      "name": "Cigarette Lighter",
                      "type": { "misc": {} },
                      "count": 1, "notes": "Windproof. Waterproof.",
                      "owners": None
                    },
                    {
                      "name": "B cell clip",
                      "type": { "misc": {} },
                      "count": 6, "notes": "", "owners": None
                    },
                    {
                      "name": "Flashlight",
                      "type": { "misc": {} },
                      "count": 1,
                      "notes": "10-yard beam. 2xS/50hrs.",
                      "owners": None
                    },
                    {
                      "name": "Pepper Spray",
                      "type": {
                        "unknown weapon": { "damage": {}, "skill": {} }
                      },
                      "count": 1, "notes": "", "owners": None, "parry": -4
                    },
                    {
                      "name": "Tear Gas Spray",
                      "type": {
                        "unknown weapon": {
                          "damage": {},
                          "skill": {}
                        }
                      },
                      "count": 1, "notes": "", "owners": None, "parry": -4
                    },
                    {
                      "name": "C Cells",
                      "type": { "misc": {} },
                      "count": 6, "notes": "P(3/9), P(8/9)",
                      "owners": None
                    },
                    {
                      "name": "Fingerbone of Luck",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    {
                      "name": "Fingerbone of Major Healing",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    {
                      "name": "Fingerbone of Teleport",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    }
                  ]
                },
                { # 6
                  "name": "Ballistic Sunglasses",
                  "type": { "armor": { "dr": 4 } },
                  "count": 1, "notes": "", "owners": None
                },
                { # 7
                  "name": "Attach\u00c3\u00a9 Case",
                  "type": { "container": {} },
                  "count": 1,
                  "notes": "",
                  "owners": None,
                  "stuff": [
                    { # 0
                      "name": "Camera, Digital, Full-Sized",
                      "type": { "misc": {} },
                      "count": 1,
                      "notes": "Photography +0. Runs for 10hrs.",
                      "owners": None
                    },
                    { # 1
                      "name": "Electronic Lockpick",
                      "type": { "misc": {} },
                      "count": 1, "notes": "A/2hr.", "owners": None
                    },
                    { # 2
                      "name": "First Aid Kit",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None,
                      "bonus": [{'amount': 1, 'name': 'First Aid', 'type': 'skill'}]
                    },
                    { # 3
                      "name": "Multi-Tool",
                      "type": { "misc": {} },
                      "count": 1, "notes": "Most repairs -5.", "owners": None
                    },
                    { # 4
                      "name": "Microfiber Towel",
                      "type": { "misc": {} },
                      "count": 1, "notes": "2'x4'", "owners": None
                    },
                    { # 5
                      "name": "Index Cards",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 6
                      "name": "Marker",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 7
                      "name": "Measuring laser",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 8
                      "name": "Nitrile Gloves",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 9
                      "name": "Plastic Bags",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 10
                      "name": "Fire-Starter Paste",
                      "type": { "misc": {} },
                      "count": 1, "notes": "Enough for 20 fires.",
                      "owners": None
                    },
                    { # 11
                      "name": "Glowstick",
                      "type": { "misc": {} },
                      "count": 1, "notes": "Lasts 12 hours.", "owners": None
                    },
                    { # 12
                      "name": "Snack",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    { # 13
                      "name": "Cards",
                      "type": { "misc": {} },
                      "count": 1,
                      "notes": "1 Conseco 2 Campanera 28Hernandez 1Sazaki 1Pasqual 2Rose",
                      "owners": None
                    },
                    { # 14
                      "name": "\"Zip Taser\" (Battery Launcher)",
                      "stuff": [],
                      "type": {
                        "container": 1,
                        "ranged weapon": {
                          "damage": {
                            "dice": {
                              "num_dice": 1,
                              "plus": 3,
                              "type": "FP"
                            }
                          },
                          "skill": {
                            "Guns (Pistol)": 0
                          }
                        }
                      },
                      "count": 1, "notes": "6/6", "owners": None,
                      "bulk": -3, "acc": 1,
                      "reload_type": 2, "reload": 3,
                      "ammo": {
                        "name": "** UNKNOWN **",
                        "shots": 6,
                        "shots_left": 6
                      }
                    },
                    { # 15
                      "name": "Heavy Zip Taser",
                      "stuff": [],
                      "type": {
                        "container": 1,
                        "ranged weapon": {
                          "damage": {
                            "dice": {
                              "num_dice": 2,
                              "plus": 0,
                              "type": "pi"
                            }
                          },
                          "skill": {
                            "Guns (Grenade Launcher)": 0
                          }
                        }
                      },
                      "count": 1, "notes": "", "owners": None,
                      "bulk": -4, "acc": 1,
                      "reload_type": 2, "reload": 4,
                      "ammo": {
                        "name": "** UNKNOWN **",
                        "shots": 6,
                        "shots_left": 6
                      }
                    }
                  ]
                },
                { # 8
                  "name": "eRubles",
                  "type": {
                    "misc": {}
                  },
                  "count": 1,
                  "notes": "218,766",
                  "owners": None
                }
              ],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "Alcohol Intolerance": -1,
                "Code of Honor (Professional)": -5,
                "Combat Reflexes": 15,
                "Dyslexia": -10,
                "G-Experience": 3,
                "High Pain Threshold": 10,
                "Night Vision": 4,
                "No Sense of Humor": -10,
                "Nosy": -1,
                "Pyromania": -5,
                "Weirdness Magnet": -15
              },
              "aim": { "braced": False, "rounds": 0 },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char5.gcs",
              "posture": "standing",
              "shock": 0,
              "skills": {
                "Acting": 7,
                "Armoury (Small Arms)": 11,
                "Axe/Mace": 14,
                "Beam Weapons (Pistol)": 17,
                "Beam Weapons (Rifle)": 18,
                "Brawling": 15,
                "Broadsword": 14,
                "Explosives (Demolition)": 14,
                "Explosives (Explosive Ordnance Disposal)": 13,
                "Fast-Draw (Ammo)": 16,
                "Fast-Draw (Pistol)": 16,
                "Fast-Talk": 13,
                "First Aid": 14,
                "Gambling": 7,
                "Guns (Grenade Launcher)": 15,
                "Guns (Pistol)": 15,
                "Holdout": 11,
                "Interrogation": 12,
                "Karate": 15,
                "Knife": 17,
                "Law (Conglomerate)": 10,
                "Lockpicking": 12,
                "Observation": 14,
                "Search": 12,
                "Stealth": 16,
                "Streetwise": 12,
                "Throwing": 15,
                "Traps": 12
              },
              "stunned": False,
              "techniques": [
                {
                  "name": "Dual-Weapon Attack",
                  "default": "Beam Weapons (Pistol)",
                  "value": -3
                },
                {
                  "name": "Off-Hand Weapon Training",
                  "default": "Beam Weapons (Pistol)",
                  "value": -4
                },
                {
                  "name": "Off-Hand Weapon Training",
                  "default": "Guns (Pistol)",
                  "value": -3
                }
              ],
              "spells": []
        },

        'unittest_import/Char6.gcs': {
              "actions_this_turn": [], "armor-index": [],
              "current": {
                "fp": 19, "iq": 16, "hp": 13, "wi": 16,
                "st": 10, "ht": 15, "dx": 8,
                "basic-move": 6, "basic-speed": 5.75, "per": 16
              },
              "current-weapon": 0, "fight-notes": [],
              "ignored-equipment": [], "notes": [],
              "open-container": [], "opponent": None,
              "permanent": {
                "fp": 19, "iq": 16, "hp": 13, "wi": 16,
                "st": 10, "ht": 15, "dx": 8,
                "basic-move": 6, "basic-speed": 5.75, "per": 16
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [
                { # 0
                  "name": "Sick Stick",
                  "type": {
                    "swung weapon": {
                      "damage": {
                        "dice": {
                          "num_dice": 1,
                          "plus": 1,
                          "type": "fat"
                        }
                      },
                      "skill": {
                        "dx": -5,
                        "Force Sword": -4,
                        "Broadsword": 0,
                        "Rapier": -4,
                        "Saber": -4,
                        "Shortsword": -2,
                        "Two-Handed Sword": -4,
                        "Axe/Mace": 0
                      }
                    }
                  },
                  "count": 1,
                  "notes": "On hit: make HT roll or vomit (out 1d/3 turns)",
                  "owners": None,
                  "parry": 0
                },
                { # 1
                  "name": "Blaster Pistol, Sig Sauer D65",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": {
                        "dice": {
                          "num_dice": 1,
                          "plus": 4,
                          "type": "pi"
                        }
                      },
                      "skill": {
                        "dx": -4,
                        "Beam Weapons (Pistol)": 0,
                        "Beam Weapons": -4,
                        "Guns (Pistol)": -4
                      }
                    }
                  },
                  "count": 1, "notes": "C/9 shots", "owners": None,
                  "bulk": -2, "acc": 4,
                  "reload_type": 2, "reload": 3,
                  "ammo": { "name": "** UNKNOWN **", "shots": 9, "shots_left": 9
                  }
                },
                { # 2
                  "name": "Laser pistol from David Smith Austin Diamond Protocol",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": {
                        "dice": {
                          "num_dice": 2,
                          "plus": 1,
                          "type": "pi"
                        }
                      },
                      "skill": {
                        "dx": -4,
                        "Beam Weapons (Pistol)": 0,
                        "Beam Weapons": -4,
                        "Guns (Pistol)": -4
                      }
                    }
                  },
                  "count": 1, "notes": "C/7 shots", "owners": None,
                  "bulk": -2, "acc": 2,
                  "reload_type": 2, "reload": 3,
                  "ammo": { "name": "** UNKNOWN **", "shots": 7, "shots_left": 7 }
                },
                { # 3
                  "name": "Papa Jorge's Blazer",
                  "type": { "misc": {} },
                  "count": 1, "notes": "-5 damage reduction.", "owners": None
                },
                { # 4
                  "name": "Plans for my character",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "Add blink, Add points to the pain spell to get to 20 so it goes faster.",
                  "owners": None
                },
                { # 5
                  "name": "C cells",
                  "type": { "misc": {} },
                  "count": 3,
                  "notes": " shots each xxxxxxx xxxxxxx in weapon: 1234567",
                  "owners": None
                },
                { # 6
                  "name": "Antitoxin Kit",
                  "type": { "misc": {} },
                  "count": 6,
                  "notes": "Antidote for specific poison. 10 uses",
                  "owners": None
                },
                { # 7
                  "name": "Antibiotic",
                  "type": { "misc": {} },
                  "count": 8,
                  "notes": "Prevents or cures (in 1d days) infections.",
                  "owners": None
                },
                { # 8
                  "name": "Bandages",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "Bandages for a  half-dozen wounds. Might be clean cloth, adhesive dressings, or spray-on \"Plastiskin\", depending on TL. Basic equipment for First Aid skill.",
                  "owners": None
                },
                { # 9
                  "name": "Backpack, Small",
                  "type": { "container": {} },
                  "count": 1, "notes": "", "owners": None,
                  "stuff": [
                    {
                      "name": "Eyeglasses",
                      "type": { "misc": {} },
                      "count": 3, "notes": "", "owners": None
                    }
                  ]
                },
                { # 10
                  "name": "First Aid Kit",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "A complete kit for treating wounds, with bandages, ointments, etc.",
                  "owners": None,
                  "bonus": [{'amount': 1, 'name': 'First Aid', 'type': 'skill'}]
                },
                { # 11
                  "name": "Orb",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 12
                  "name": "Teddy Bear",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 13
                  "name": "Armor ",
                  "type": { "armor": { "dr": 5 }
                  },
                  "count": 1, "notes": "", "owners": None
                },
                { # 14
                  "name": "Erubles (divide by 20 for dollars)",
                  "type": { "misc": {} },
                  "count": 100000, "notes": "", "owners": None
                },
                { # 15
                  "name": "fog fingerbone",
                  "type": { "misc": {} },
                  "count": 2, "notes": "", "owners": None
                },
                { # 16
                  "name": "Large Knife",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 17
                  "name": "Brown finger bone of utter dome",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 18
                  "name": "Heavy heal patch2",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "2d healing for 1d6 hours if magically healed in that time it is permanent",
                  "owners": None
                },
                { # 19
                  "name": "Karen's cobbled together version of the Belt Holster from Master Library",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                }
              ],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "Agoraphobia (Open Spaces)": -10,
                "Ailurophobia (Cats)": -5,
                "Bad Sight (Farsighted)": -25,
                "Compulsive Vowing": -5,
                "Curious": -5,
                "Delusions": -1,
                "Distractible": -1,
                "I took two air spells which are from a disallowed college": -1,
                "Impulsiveness": -10,
                "Like Shiny objects": -1,
                "Lwa (Bokor)": 8,
                "Personality Change": -1,
                "Responsive": -1,
                "Vodou Practitioner": 45
              },
              "aim": { "braced": False, "rounds": 0 },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char6.gcs",
              "posture": "standing", "shock": 0,
              "skills": {
                "Beam Weapons (Pistol)": 14,
                "Fast-Draw (Pistol)": 9,
                "First Aid": 17,
                "Law (Conglomerate, Trans territorial jurisdiction/the void)": 14,
                "Physician": 14
              },
              "stunned": False, "techniques": [],
              "spells": [
                { "name": "Agonize", "skill": 15 },
                { "name": "Analyze Magic", "skill": 14 },
                { "name": "Compel Truth", "skill": 14 },
                { "name": "Conceal Magic", "skill": 14 },
                { "name": "Control Person", "skill": 14 },
                { "name": "Control Zombie", "skill": 16 },
                { "name": "Counterspell", "skill": 14 },
                { "name": "Cure Disease", "skill": 15 },
                { "name": "Death Vision", "skill": 16 },
                { "name": "Detect Magic", "skill": 14 },
                { "name": "Dispel Magic", "skill": 14 },
                { "name": "Dispel Possession", "skill": 14 },
                { "name": "Enchant", "skill": 13 },
                { "name": "Fear", "skill": 14 },
                { "name": "Identify Spell", "skill": 14 },
                { "name": "Itch", "skill": 15 },
                { "name": "Lend Energy", "skill": 15 },
                { "name": "Lend Vitality", "skill": 15 },
                { "name": "Light", "skill": 14 },
                { "name": "Major Healing", "skill": 14 },
                { "name": "Mind-Reading", "skill": 14 },
                { "name": "Mind-Search", "skill": 13 },
                { "name": "Minor Healing", "skill": 15 },
                { "name": "Pain", "skill": 15 },
                { "name": "Possession", "skill": 13 },
                { "name": "Powerstone", "skill": 14 },
                { "name": "Purify Air", "skill": 14 },
                { "name": "Recover Energy", "skill": 15 },
                { "name": "Regeneration", "skill": 14 },
                { "name": "Relieve Sickness", "skill": 15 },
                { "name": "Resist Pain", "skill": 15 },
                { "name": "Restoration", "skill": 14 },
                { "name": "Seek Machine", "skill": 14 },
                { "name": "Seek Plant", "skill": 14 },
                { "name": "Sense Emotion", "skill": 14 },
                { "name": "Sense Foes", "skill": 14 },
                { "name": "Sensitize", "skill": 15 },
                { "name": "Share Energy", "skill": 15 },
                { "name": "Share Vitality", "skill": 15 },
                { "name": "Shield", "skill": 14 },
                { "name": "Soul Rider", "skill": 14 },
                { "name": "Spasm", "skill": 15 },
                { "name": "Steal Energy", "skill": 16 },
                { "name": "Steal Vitality", "skill": 16 },
                { "name": "Stun", "skill": 15 },
                { "name": "Summon Spirit", "skill": 16 },
                { "name": "Teleport", "skill": 13 },
                { "name": "Terror", "skill": 14 },
                { "name": "Truthsayer", "skill": 14 },
                { "name": "Turn Zombie", "skill": 16 },
                { "name": "Zombie", "skill": 16 }
              ]
        },

        'unittest_import/Char7.gcs': {
              "actions_this_turn": [],
              "armor-index": [],
              "current": {
                "fp": 30, "iq": 12, "hp": 12, "wi": 12,
                "st": 9, "ht": 13, "dx": 15,
                "basic-move": 8, "basic-speed": 8.0, "per": 12
              },
              "current-weapon": 0,
              "fight-notes": [],
              "ignored-equipment": [],
              "notes": [],
              "open-container": [],
              "opponent": None,
              "permanent": {
                "fp": 30, "iq": 12, "hp": 12, "wi": 12,
                "st": 9, "ht": 13, "dx": 15,
                "basic-move": 8, "basic-speed": 8.0, "per": 12
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "Combat Reflexes": 15,
                "Natural Attacks": 0,
                "Empathy": 15,
                "High Pain Threshold": 10,
                "Vodou Practitioner": 35,
                "Lwa (Bokor)": 8
              },
              "aim": { "braced": False, "rounds": 0 },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char7.gcs",
              "posture": "standing",
              "shock": 0,
              "skills": {},
              "stunned": False,
              "techniques": [],
              "spells": []
        },

        'unittest_import/Char8.gcs': {
              "actions_this_turn": [],
              "armor-index": [],
              "current": {
                "fp": 14, "iq": 11, "hp": 14, "wi": 13,
                "st": 12, "ht": 12, "dx": 14,
                "basic-move": 6, "basic-speed": 6.5, "per": 11
              },
              "current-weapon": 0, "fight-notes": [], "ignored-equipment": [],
              "notes": [], "open-container": [], "opponent": None,
              "permanent": {
                "fp": 14, "iq": 11, "hp": 14, "wi": 13,
                "st": 12, "ht": 12, "dx": 14,
                "basic-move": 6, "basic-speed": 6.5, "per": 11
              },
              "preferred-armor-index": [], "preferred-weapon-index": [],
              "state": "alive",
              "stuff": [
                { # 0
                  "name": "Armor",
                  "type": { "armor": { "dr": 5 }
                  },
                  "count": 1,
                  "notes": "Currently support garment and ablative (dr5) abaltive, (dr5) balistic, ",
                  "owners": None
                },
                { # 1
                  "name": "Belt",
                  "type": { "container": {} },
                  "count": 1,
                  "notes": "",
                  "owners": None,
                  "stuff": [
                    {
                      "name": "Large Sheath",
                      "type": {
                        "container": {}
                      },
                      "count": 1,
                      "notes": "",
                      "owners": None,
                      "stuff": [
                        {
                          "name": "Large Knife",
                          "type": {
                            "swung weapon": {
                              "damage": {
                                "st": "sw",
                                "plus": -2,
                                "type": "cut"
                              },
                              "skill": {
                                "DX": -4,
                                "Knife": 0,
                                "Force Sword": -3,
                                "Main-Gauche": -3,
                                "Shortsword": -3,
                                "Sword!": 0
                              }
                            },
                            "thrust weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": 0,
                                "type": "imp"
                              },
                              "skill": {
                                "DX": -4,
                                "Knife": 0,
                                "Force Sword": -3,
                                "Main-Gauche": -3,
                                "Shortsword": -3,
                                "Sword!": 0
                              }
                            },
                            "ranged weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": 0,
                                "type": "imp"
                              },
                              "skill": {
                                "DX": -4,
                                "Thrown Weapon (Knife)": 0
                              }
                            }
                          },
                          "count": 1,
                          "notes": "",
                          "owners": None,
                          "parry": -1,
                          "bulk": -2,
                          "acc": 0,
                          "reload_type": 0
                        }
                      ]
                    },
                    {
                      "name": "Small Sheath",
                      "type": { "container": {} },
                      "count": 1,
                      "notes": "",
                      "owners": None,
                      "stuff": [
                        {
                          "name": "Boots",
                          "type": { "armor": { "dr": 2 } },
                          "count": 1,
                          "notes": "",
                          "owners": None
                        },
                        {
                          "name": "Small Knife",
                          "type": {
                            "swung weapon": {
                              "damage": {
                                "st": "sw",
                                "plus": -3,
                                "type": "cut"
                              },
                              "skill": {
                                "DX": -4,
                                "Knife": 0,
                                "Force Sword": -3,
                                "Main-Gauche": -3,
                                "Shortsword": -3,
                                "Sword!": 0
                              }
                            },
                            "thrust weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": -1,
                                "type": "imp"
                              },
                              "skill": {
                                "DX": -4,
                                "Knife": 0,
                                "Force Sword": -3,
                                "Main-Gauche": -3,
                                "Shortsword": -3,
                                "Sword!": 0
                              }
                            },
                            "ranged weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": -1,
                                "type": "imp"
                              },
                              "skill": { "DX": -4, "Thrown Weapon (Knife)": 0 }
                            }
                          },
                          "count": 1,
                          "notes": "",
                          "owners": None,
                          "parry": -1,
                          "bulk": -1,
                          "acc": 0,
                          "reload_type": 0
                        }
                      ]
                    },
                    {
                      "name": "Tactical Belt Bag",
                      "type": { "container": {} },
                      "count": 1,
                      "notes": "",
                      "owners": None,
                      "stuff": [
                        {
                          "name": "Brass Knuckles",
                          "type": {
                            "unknown weapon": {
                              "damage": {
                                "st": "thr",
                                "plus": 0,
                                "type": "cr"
                              },
                              "skill": {
                                "DX": 0,
                                "Boxing": 0,
                                "Brawling": 0,
                                "Karate": 0
                              }
                            }
                          },
                          "count": 1,
                          "notes": "",
                          "owners": None,
                          "parry": 0
                        }
                      ]
                    }
                  ]
                },
                { # 2
                  "name": "Cigarette Lighter (Metal Refillable)",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 3
                  "name": "Conglomerate Marshal Uniform",
                  "type": { "misc": {} },
                  "count": 1, "notes": "", "owners": None
                },
                { # 4
                  "name": "E-Rubles",
                  "type": { "misc": {} },
                  "count": 24600, "notes": "", "owners": None
                },
                { # 5
                  "name": "Laser Rifle",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": {
                        "dice": { "num_dice": 3, "plus": 0, "type": "pi" }
                      },
                      "skill": { "DX": -4, "Beam Weapons (Rifle)": 0 }
                    }
                  },
                  "count": 1, "notes": "", "owners": None,
                  "bulk": -4, "acc": 8,
                  "reload_type": 2, "reload": 3,
                  "ammo": { "name": "** UNKNOWN **", "shots": 10, "shots_left": 10 }
                },
                { # 6
                  "name": "Holster, Shoulder",
                  "type": { "container": {} },
                  "count": 1,
                  "notes": "Allows use of Holdout, but gives -1 to Fast-Draw.",
                  "owners": None,
                  "stuff": [
                    { # 0
                      "name": "Blaster Pistol, Sig Sauer D65",
                      "stuff": [],
                      "type": {
                        "container": 1,
                        "ranged weapon": {
                          "damage": {
                            "dice": { "num_dice": 1, "plus": 4, "type": "fat" }
                          },
                          "skill": {
                            "DX": -4, "Beam Weapons (Pistol)": 0,
                            "Beam Weapons": -4, "Guns (Pistol)": -4
                          }
                        }
                      },
                      "count": 1,
                      "notes": "C/9 shots",
                      "owners": None,
                      "bulk": -2,
                      "acc": 4,
                      "reload_type": 2, "reload": 3,
                      "ammo": { "name": "** UNKNOWN **",
                                "shots": 9, "shots_left": 9 }
                    }
                  ]
                },
                { # 7
                  "name": "Blaster Pistol, Sig Sauer D65",
                  "stuff": [],
                  "type": {
                    "container": 1,
                    "ranged weapon": {
                      "damage": {
                        "dice": { "num_dice": 1, "plus": 4, "type": "fat" }
                      },
                      "skill": {
                        "DX": -4, "Beam Weapons (Pistol)": 0,
                        "Beam Weapons": -4, "Guns (Pistol)": -4
                      }
                    }
                  },
                  "count": 1, "notes": "C/9 shots", "owners": None,
                  "bulk": -2, "acc": 4,
                  "reload_type": 2, "reload": 3,
                  "ammo": { "name": "** UNKNOWN **", "shots": 9, "shots_left": 9 }
                },
                { # 8
                  "name": "Medicine Bag",
                  "type": { "misc": {} },
                  "count": 1,
                  "notes": "",
                  "owners": None
                },
                { # 9
                  "name": "Messenger Bag/Shoulder Bag",
                  "type": { "container": {} },
                  "count": 1,
                  "notes": "",
                  "owners": None,
                  "stuff": [
                    {
                      "name": "First Aid Kit",
                      "type": { "misc": {} },
                      "count": 1,
                      "notes": "A complete kit for treating wounds, with bandages, ointments, etc.",
                      "owners": None,
                      "bonus": [{'amount': 1, 'name': 'First Aid', 'type': 'skill'}]
                    },
                    {
                      "name": "Sick Stick",
                      "type": {
                        "swung weapon": {
                          "damage": {
                            "dice": {
                              "num_dice": 1,
                              "plus": 1,
                              "type": "fat"
                            }
                          },
                          "skill": {
                            "DX": -5,
                            "Force Sword": -4,
                            "Broadsword": 0,
                            "Rapier": -4,
                            "Saber": -4,
                            "Shortsword": -2,
                            "Two-Handed Sword": -4,
                            "Axe/Mace": 0
                          }
                        }
                      },
                      "count": 1,
                      "notes": "On hit: make HT roll or vomit (out 1d/3 turns)",
                      "owners": None,
                      "parry": 0
                    }
                  ]
                },
                { # 10
                  "name": "C cell",
                  "type": { "misc": {} },
                  "count": 3,
                  "notes": "",
                  "owners": None
                },
                { # 11
                  "name": "Heavy Heal Patch",
                  "type": { "misc": {} },
                  "count": 2,
                  "notes": "Heals 2D for 1D hours",
                  "owners": None
                },
                { # 12
                  "name": "Finger Bones",
                  "type": { "container": {} },
                  "count": 1, "notes": "", "owners": None,
                  "stuff": [
                    {
                      "name": "Body of Metal - Finger Bone (black)",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    {
                      "name": "Major Heal - Finger Bone (green)",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    },
                    {
                      "name": "Teleport - Finger Bone",
                      "type": { "misc": {} },
                      "count": 1, "notes": "", "owners": None
                    }
                  ]
                }
              ],
              "timers": [],
              "weapon-index": [],
              "advantages": {
                "G-Experience": 1,
                "Combat Reflexes": 15,
                "Fit": 5,
                "Rapid Healing": 5,
                "Vodou Practitioner": 5,
                "Enemy (Gregory Occeant/Loveson Jabouin)": -20,
                "Flashbacks (Mild, -2, 2D seconds)": -5,
                "Guilt Complex (loss of sister)": -5,
                "Light Sleeper": -5,
                "Vow (Return to Earth and find sister)": -5,
                "Wealth": -10,
                "Dislikes Drugs": -1,
                "Like Excercise": -1,
                "Staid": -1,
                "Uncongenial": -1
              },
              "aim": {
                "braced": False,
                "rounds": 0
              },
              "check_for_death": False,
              "gcs-file": "unittest_import/Char8.gcs",
              "posture": "standing",
              "shock": 0,
              "skills": {
                "Armoury (Small Arms)": 11,
                "Axe/Mace (Sick Stick)": 14,
                "Beam Weapons (Pistol)": 19,
                "Beam Weapons (Rifle)": 17,
                "Brawling": 16,
                "Camouflage": 11,
                "Climbing": 15,
                "Fast-Draw (Knife)": 15,
                "Fast-Draw (Pistol)": 17,
                "Filch": 13,
                "First Aid": 13,
                "Gesture": 11,
                "Intimidation": 15,
                "Knife": 15,
                "Law (Conglomerate, trans-territorial jurisdiction/the void)": 9,
                "Lockpicking": 10,
                "Pickpocket": 12,
                "Running": 11,
                "Scrounging": 12,
                "Stealth": 15,
                "Streetwise": 11,
                "Theology (Vodun)": 11,
                "Throwing": 15,
                "Urban Survival": 11
              },
              "stunned": False,
              "techniques": [],
              "spells": []
            }
    }

    def test_import_character(self):
        test_cases = [
                'unittest_import/Char1.gcs',
                'unittest_import/Char2.gcs',
                'unittest_import/Char3.gcs',
                'unittest_import/Char4.gcs',
                'unittest_import/Char5.gcs',
                'unittest_import/Char6.gcs',
                'unittest_import/Char7.gcs',
                'unittest_import/Char8.gcs',
            ]
        stdscr = curses.initscr() # needed for stuff in ca_gcs_import.py
        curses.start_color()
        curses.use_default_colors()

        for test_case in test_cases:
            self.debug.header1('TEST: %s' % test_case)

            self._window_manager.set_menu_response('Add Which Equipment',
                    {'op': ca_gcs_import.ToNative.EQUIP_ADD_ALL})

            name, creature = self._ruleset.import_creature_from_file(test_case)
            diff = diff_json.DiffJson('Test (%s)' % test_case,
                                      'Expected',
                                      verbose=False)
            if not diff.are_equal(creature,
                                  GmTestCaseImport.good_data[test_case],
                                  ''):
                self.debug.header2('TEST: %s' % test_case)
                self.debug.pprint(creature)
                self.debug.header2('EXPECTED')
                self.debug.pprint(GmTestCaseImport.good_data[test_case])
                assert(0) # just to raise the exception
