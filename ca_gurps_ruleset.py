#! /usr/bin/python

import copy
import curses
import random

import ca_fighter
import ca_equipment
import ca_gui
import ca_ruleset
import ca_timers

class GurpsRuleset(ca_ruleset.Ruleset):
    '''
    GURPS is a trademark of Steve Jackson Games, and its rules and art are
    copyrighted by Steve Jackson Games. All rights are reserved by Steve
    Jackson Games. This game aid is the original creation of Wade Guthrie and
    is released for free distribution, and not for resale, under the
    permissions granted in the
    <a href="http://www.sjgames.com/general/online_policy.html">Steve Jackson
    Games Online Policy</a>.

    Steve Jackson Games appears to allow the creation of a "Game Aid" which is
    PC-based and not a phone or tablet app.  This is done in
    http://sjgames.com/general/online_policy.html. The relevant text is as
    follows:

        "If you mean [by 'So, does that mean I can...Create a character
        generator or other game aid?] a "game aid" or "player aid" program,
        yes, you certainly can, if it's for a PC-type computer and you
        include the appropriate notices. We currently do not allow "apps"
        for mobile devices to be created using our content or trademarks. [...]

        We want to ENCOURAGE our fans to create these programs, share them
        with the community, and have fun doing it. If you want to charge money
        for a game aid based on our work, the Online Policy does NOT apply
        . . . you must either get a license from us, or sell us the game aid
        for distribution as a regular product, and either way we'll hold you
        to professional standards. Email licensing@sjgames.com with a formal
        proposal letter."

    So, we're not charging, we're not putting this on a mobile device, and the
    appropriate notices are included above, so we _should_ be good.  I've
    included the notice at the beginning of this class because it is my intent
    to compartmentalize all GURPS-specific stuff in this class.  The rest of
    this program is (supposed to be) generic.

    This is a place for all of the ruleset (GURPS, in this case) specific
    stuff.

    In addition to what's required by 'Ruleset', each character's dict is
    expected to look like this:
    {
        'aim': {'rounds': <number>, 'braced': True | False}
        'shock': <number, 0 for 'None'>
        'dodge' : <final dodge value (including things like 'Enhanced Dodge'>
        'skills': { <skill name> : <final skill value>, ...}
        'current': { <attribute name> : <final attribute value>, ... }
            These are: 'fp', 'hp', 'iq', 'ht', 'st', 'dx', and 'basic-speed'
        'permanent': { <same attributes as in 'current'> }
        'check_for_death': True | False
    }

    Weapon looks like:
    {
        TBS
        'type': <melee weapon> | <ranged weapon> | <shield>
        'parry': <plus to parry>
    }

    'Final' values include any plusses due to advantages or skills or
    whaterver.  This code doesn't calculate any of the derived values.  This
    may change in the future, however.
    '''

    damage_mult = { 'burn': 1.0, 'cor': 1.0, 'cr':  1.0, 'cut': 1.5,
                    'imp':  2.0, 'pi-': 0.5, 'pi':  1.0, 'pi+': 1.5,
                    'pi++': 2.0, 'tbb': 1.0, 'tox': 1.0
                  }
    melee_damage = {1:  {'thr': {'num_dice': 1, 'plus': -6},
                         'sw':  {'num_dice': 1, 'plus': -5}},
                    2:  {'thr': {'num_dice': 1, 'plus': -6},
                         'sw':  {'num_dice': 1, 'plus': -5}},
                    3:  {'thr': {'num_dice': 1, 'plus': -5},
                         'sw':  {'num_dice': 1, 'plus': -4}},
                    4:  {'thr': {'num_dice': 1, 'plus': -5},
                         'sw':  {'num_dice': 1, 'plus': -4}},
                    5:  {'thr': {'num_dice': 1, 'plus': -4},
                         'sw':  {'num_dice': 1, 'plus': -3}},
                    6:  {'thr': {'num_dice': 1, 'plus': -4},
                         'sw':  {'num_dice': 1, 'plus': -3}},
                    7:  {'thr': {'num_dice': 1, 'plus': -3},
                         'sw':  {'num_dice': 1, 'plus': -2}},
                    8:  {'thr': {'num_dice': 1, 'plus': -3},
                         'sw':  {'num_dice': 1, 'plus': -2}},
                    9:  {'thr': {'num_dice': 1, 'plus': -2},
                         'sw':  {'num_dice': 1, 'plus': -1}},
                    10: {'thr': {'num_dice': 1, 'plus': -2},
                         'sw':  {'num_dice': 1, 'plus': 0}},
                    11: {'thr': {'num_dice': 1, 'plus': -1},
                         'sw':  {'num_dice': 1, 'plus': +1}},
                    12: {'thr': {'num_dice': 1, 'plus': -1},
                         'sw':  {'num_dice': 1, 'plus': +2}},
                    13: {'thr': {'num_dice': 1, 'plus': 0},
                         'sw':  {'num_dice': 2, 'plus': -1}},
                    14: {'thr': {'num_dice': 1, 'plus': 0},
                         'sw':  {'num_dice': 2, 'plus': 0}},
                    15: {'thr': {'num_dice': 1, 'plus': +1},
                         'sw':  {'num_dice': 2, 'plus': +1}},
                    16: {'thr': {'num_dice': 1, 'plus': +1},
                         'sw':  {'num_dice': 2, 'plus': +2}},
                    17: {'thr': {'num_dice': 1, 'plus': +2},
                         'sw':  {'num_dice': 3, 'plus': -1}},
                    18: {'thr': {'num_dice': 1, 'plus': +2},
                         'sw':  {'num_dice': 3, 'plus': 0}},
                    19: {'thr': {'num_dice': 2, 'plus': -1},
                         'sw':  {'num_dice': 3, 'plus': +1}},
                    20: {'thr': {'num_dice': 2, 'plus': -1},
                         'sw':  {'num_dice': 3, 'plus': +2}},
                    21: {'thr': {'num_dice': 2, 'plus': 0},
                         'sw':  {'num_dice': 4, 'plus': -1}},
                    22: {'thr': {'num_dice': 2, 'plus': 0},
                         'sw':  {'num_dice': 4, 'plus': 0}},
                    23: {'thr': {'num_dice': 2, 'plus': +1},
                         'sw':  {'num_dice': 4, 'plus': +1}},
                    24: {'thr': {'num_dice': 2, 'plus': +1},
                         'sw':  {'num_dice': 4, 'plus': +2}},
                    25: {'thr': {'num_dice': 2, 'plus': +2},
                         'sw':  {'num_dice': 5, 'plus': -1}}
                         }

    abilities = {
        'skills': {
            # 'name': {'ask': 'number' | 'string' }
            #         {'value': value}
            "Acting": {'ask': 'number'},
            "Area Knowledge (Space Station)": {'ask': 'number'},
            "Armoury (Heavy Weapons)": {'ask': 'number'},
            "Armoury (Small Arms)": {'ask': 'number'},
            "Axe/Mace": {'ask': 'number'},
            "Bartender": {'ask': 'number'},
            "Beam Weapons (Pistol)": {'ask': 'number'},
            "Beam Weapons (Rifle)": {'ask': 'number'},
            "Brawling": {'ask': 'number'},
            "Camouflage": {'ask': 'number'},
            "Climbing": {'ask': 'number'},
            "Climbing": {'ask': 'number'},
            "Computer Hacking": {'ask': 'number'},
            "Computer Operation": {'ask': 'number'},
            "Computer Programming": {'ask': 'number'},
            "Connoisseur (Visual Arts)": {'ask': 'number'},
            "Cryptography": {'ask': 'number'},
            "Current Affairs (Teraforming)": {'ask': 'number'},
            "Detect Lies": {'ask': 'number'},
            "Diplomacy": {'ask': 'number'},
            "Electronics Operation (Security)": {'ask': 'number'},
            "Electronics Operation (Teraforming)": {'ask': 'number'},
            "Electronics Repair (Security)": {'ask': 'number'},
            "Electronics Repair (Teraforming)": {'ask': 'number'},
            "Engineer (Electronics)": {'ask': 'number'},
            "Engineer (Starships)": {'ask': 'number'},
            "Escape": {'ask': 'number'},
            "Expert Skill (Computer Security)": {'ask': 'number'},
            "Fast-Draw (Ammo)": {'ask': 'number'},
            "Fast-Draw (Knife)": {'ask': 'number'},
            "Fast-Draw (Pistol)": {'ask': 'number'},
            "Fast-Talk": {'ask': 'number'},
            "Filch": {'ask': 'number'},
            "First Aid": {'ask': 'number'},
            "Forensics": {'ask': 'number'},
            "Forgery": {'ask': 'number'},
            "Gambling": {'ask': 'number'},
            "Gesture": {'ask': 'number'},
            "Gunner (Beams)": {'ask': 'number'},
            "Gunner (Cannon)": {'ask': 'number'},
            "Guns (Grenade Launcher)": {'ask': 'number'},
            "Guns (Pistol)": {'ask': 'number'},
            "Hazardous Materials (Chemical)": {'ask': 'number'},
            "Holdout": {'ask': 'number'},
            "Interrogation": {'ask': 'number'},
            "Intimidation": {'ask': 'number'},
            "Karate": {'ask': 'number'},
            "Knife": {'ask': 'number'},
            "Law (Conglomerate)": {'ask': 'number'},
            "Law (Conglomerate, Trans territorial jurisdiction/the void)":
            {'ask': 'number'},
            "Lip Reading": {'ask': 'number'},
            "Lockpicking": {'ask': 'number'},
            "Mathematics (Applied)": {'ask': 'number'},
            "Mechanic (Spacecraft)": {'ask': 'number'},
            "Observation": {'ask': 'number'},
            "Physician": {'ask': 'number'},
            "Physics": {'ask': 'number'},
            "Pickpocket": {'ask': 'number'},
            "Piloting (Loader Mech)": {'ask': 'number'},
            "Piloting (Low-Performance Spacecraft)": {'ask': 'number'},
            "Running": {'ask': 'number'},
            "Scrounging": {'ask': 'number'},
            "Search": {'ask': 'number'},
            "Stealth": {'ask': 'number'},
            "Streetwise": {'ask': 'number'},
            "Theology (Vodun)": {'ask': 'number'},
            "Throwing": {'ask': 'number'},
            "Thrown Weapon (Knife)": {'ask': 'number'},
            "Tonfa": {'ask': 'number'},
            "Traps": {'ask': 'number'},
            "Urban Survival": {'ask': 'number'},
        },
        'advantages': {
            "Acute Vision": {'ask': 'number'},
            "Phobia": {'ask': 'string'},
            "Alcohol Intolerance": {'value': -1},
            "Appearance": {'ask': 'string'},
            "Bad Sight": {'value': -25},
            "Bad Temper": {'value': -10},
            "Cannot Speak": {'value': -10},
            "Channeling": {'value': 10},
            "Code of Honor": {'ask': 'string'},
            "Combat Reflexes": {'value': 15},
            "Compulsive Behavior": {'ask': 'string'},
            "Cultural Familiarity": {'ask': 'string'},
            "Curious": {'value': -5},
            "Deep Sleeper": {'value': 1},
            "Delusions": {'ask': 'string'},
            "Distractible": {'value': 1},
            "Dreamer": {'value': -1},
            "Dyslexia": {'value': -10},
            "Eidetic Memory": {'ask': 'number'},
            "Empathy": {'ask': 'number'},
            "Enemy": {'ask': 'string'},
            "Extra Hit Points": {'ask': 'number'},
            "Fit": {'value': 5},
            "Flashbacks": {'ask': 'string'},
            "G-Experience": {'ask': 'number'},
            "Guilt Complex": {'ask': 'string'},
            "Habit": {'ask': 'string'},
            "High Pain Threshold": {'value': 10},
            "Honest Face": {'value': 1},
            "Humble": {'value', -1},
            "Impulsiveness": {'ask': 'number'},
            "Light Sleeper": {'value': -5},
            "Like (Quirk) ": {'ask': 'string'},
            "Lwa": {'ask': 'string'},
            "Night Vision": {'ask': 'number'},
            "No Sense of Humor": {'value': -10},
            "Nosy": {'value': -1},
            "Personality Change": {'ask': 'string'},
            "Pyromania": {'value': -10},
            "Rapid Healing": {'value': 5},
            "Responsive": {'value': -1},
            "Secret": {'ask': 'string'},
            "Short Attention Span": {'value': -10},
            "Squeamish": {'value': -10},
            "Versatile": {'value': 5},
            "Vodou Practitioner (level 0)": {'value': 5},
            "Vodou Practitioner (Mambo/Hougan 1)": {'value': 15},
            "Vodou Practitioner (Mambo/Hougan 2)": {'value': 35},
            "Vodou Practitioner (Mambo/Hougan 3)": {'value': 65},
            "Vodou Practitioner (Bokor 1)": {'value': 20},
            "Vodou Practitioner (Bokor 2)": {'value': 45},
            "Vodou Practitioner (Bokor 3)": {'value': 75},
            "Vow": {'ask': 'string'},
            "Wealth": {'ask': 'string'},
            "Weirdness Magnet": {'value': -15},
        }
    }

    # These are specific to the Persephone version of the GURPS ruleset
    spells = {

        # Alphabetized for conevenience

        "Agonize": {
          "cost": 8,
          "notes": "M40, HT negates",
          "maintain": 6,
          "casting time": 1,
          "duration": 60,
        },
        "Alarm": {
          "cost": 1,
          "notes": "M100",
          "maintain": 0,
          "casting time": 1,
          "duration": 604800,   # one week
        },
        "Alter Visage": {
          "cost": 4,
          "notes": "M41",
          "maintain": 0,
          "casting time": 60,
          "duration": 3600,
        },
        "Analyze Magic": {
          "cost": 8,
          "notes": "M102",
          "maintain": None,
          "casting time": 3600,
          "duration": 0,    # Instant
        },
        "Animate Shadow": {
          "cost": 4,
          "notes": "M154, Subject's shadow attacks them, HT negates",
          "maintain": 4,
          "casting time": 2,
          "duration": 5,
        },
        "Armor": {
          "cost": None,
          "notes": "M167, 2xDR, lasts 1 minute",
          "maintain": 0,
          "casting time": 1,
          "duration": 60,
        },
        "Awaken": {
          "cost": 1,
          "notes": "M90",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Bless Plants": {
          "cost": 1,
          "notes": "M161",
          "maintain": 4,
          "casting time": 300,
          "duration": 0,    # One season - no need to keep track
        },
        "Blink": {
          "cost": 2,
          "notes": "M148",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Boost Dexterity": {
          "cost": 1,
          "notes": "M37",
          "maintain": 2,
          "casting time": 1,
          "duration": 0,
        },
        "Bravery": {
          "cost": 2,
          "notes": "M134",
          "maintain": 2,
          "casting time": 1,
          "duration": 3600,
        },
        "Charm": {
          "cost": 6,
          "notes": "M139, vs. Will",
          "maintain": 3,
          "casting time": 1,
          "duration": 60,
        },
        "Choke": {
          "cost": 4,
          "notes": "M40, vs. HT",
          "maintain": 0,
          "casting time": 1,
          "duration": 30,
        },
        "Climbing": {
          "cost": 1,
          "notes": "M35",
          "maintain": 0,
          "casting time": 1,
          "duration": 60,
        },
        "Clumsiness": {
          "cost": 1,
          "notes": "M36",
          "maintain": None,
          "casting time": 1,
          "duration": 60,
        },
        "Command": {
          "cost": 4,
          "notes": "M136, vs. Will",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Communicate": {
          "cost": 4,
          "notes": "M48",
          "maintain": 4,
          "casting time": 4,
          "duration": 60,
        },
        "Conceal Magic": {
          "cost": 1,
          "notes": "M122",
          "maintain": None,
          "casting time": 3,
          "duration": 36000,    # 10 hours
        },
        "Cure Disease": {
          "cost": 4,
          "notes": "M91",
          "maintain": 2,
          "casting time": 600,
          "duration": 0,
        },
        "Daze": {
          "cost": 3,
          "notes": "M134",
          "maintain": 2,
          "casting time": 2,
          "duration": 60,
        },
        "Death Touch": {
          "cost": None,
          "notes": "M41, 1-3, needs touch",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Death Vision": {
          "cost": 2,
          "notes": "M149, vs. IQ",
          "maintain": None,
          "casting time": 3,
          "duration": 1,
        },
        "Detect Magic": {
          "cost": 2,
          "notes": "M101",
          "maintain": None,
          "casting time": 300,
          "duration": 0,
        },
        "Emotion Control": {
          "cost": 2,
          "notes": "M137",
          "maintain": 0,
          "casting time": 1,
          "duration": 3600,
        },
        "Enchant": {
          "cost": None,
          "notes": "M56",
          "maintain": None,
          "casting time": 1,
          "duration": 0,    # Permanent - no need to track
        },
        "Enslave": {
          "cost": 30,
          "notes": "M141, vs. Will",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,    # Permanent - no need to track
        },
        "Evisceration": {
          "cost": 10,
          "notes": "M154, HT/IQ negates, Magery 3",
          "maintain": 0,
          "casting time": 5,
          "duration": 0,
        },
        "Explosive Lightning": {
          "cost": None,
          "notes": "M196, cost 2-mage level, damage 1d-1 /2",
          "maintain": 0,
          "casting time": None,
          "duration": 0,
        },
        "False Memory": {
          "cost": 3,
          "notes": "M139, vs. Will",
          "maintain": 0,
          "casting time": 5,
          "duration": None,  # Ask
        },
        "Far Hearing": {
          "cost": 4,
          "notes": "M173",
          "maintain": 2,
          "casting time": 3,
          "duration": 60,
        },
        "Fear": {
          "cost": 1,
          "notes": "M134",
          "maintain": None,
          "casting time": 1,
          "duration": 36000,    # 10 minutes
        },
        "Fog": {
          "cost": None,
          "notes": "M193, cost: 2/yard radius, lasts 1 minute",
          "maintain": 0,
          "casting time": 1,
          "duration": 60,
        },
        "Foolishness": {
          "cost": None,
          "notes": "M134",
          "maintain": None,
          "casting time": 1,
          "duration": 60,
        },
        "Fumble": {
          "cost": 3,
          "notes": "M38",
          "maintain": None,
          "casting time": 1,
          "duration": 0,
        },
        "Golem": {
          "cost": 250,
          "notes": "M59",
          "maintain": 0,
          "casting time": 0,
          "duration": 0,    # Permanent -- no need to track
        },
        "Grace": {
          "cost": 4,
          "notes": "M37",
          "maintain": None,
          "casting time": 1,
          "duration": 60,
        },
        "Great Ward": {
          "cost": None,
          "notes": "M122, cost: 1/person (min:4)",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Hair Growth": {
          "cost": 1,
          "notes": "M39",
          "maintain": None,
          "casting time": 1,
          "duration": 5,
        },
        "Haircut": {
          "cost": 2,
          "notes": "M39",
          "maintain": None,
          "casting time": 2,
          "duration": 0,
        },
        "Heal Plant": {
          "cost": 3,
          "notes": "M161",
          "maintain": None,
          "casting time": 60,
          "duration": 0,    # Permanent -- no need to track
        },
        "Identify Plant": {
          "cost": 2,
          "notes": "M161",
          "maintain": None,
          "casting time": 1,
          "duration": 0,
        },
        "Identify Spell": {
          "cost": 2,
          "notes": "M102",
          "maintain": None,
          "casting time": 1,
          "duration": 0,
        },
        "Itch": {
          "cost": 2,
          "notes": "M35",
          "maintain": None,
          "casting time": 1,
          "duration": None,  # Ask
        },
        "Lend Energy": {
          "cost": None,
          "notes": "M89",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,    # Permanent -- no need to track
        },
        "Lend Vitality": {
          "cost": None,
          "notes": "M89",
          "maintain": None,
          "casting time": 1,
          "duration": 3600,
        },
        "Lesser Geas": {
          "cost": 12,
          "notes": "M140, vs. Will ",
          "maintain": 0,
          "casting time": 30,
          "duration": 0,    # Permanent -- no need to track
        },
        "Light": {
          "cost": 1,
          "notes": "M110",
          "maintain": 0,
          "casting time": 1,
          "duration": 60,
        },
        "Lightning": {
          "cost": None,
          "notes": "M196, cost 1-3, cast=cost, needs an attack",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Lightning Whip": {
          "cost": None,
          "notes": "M196, cost 1 per 2 yards reach",
          "maintain": 0,
          "casting time": 1,
          "duration": 10,
        },
        "Loyalty": {
          "cost": 2,
          "notes": "M136",
          "maintain": None,
          "casting time": 1,
          "duration": 3600,
        },
        "Luck": {
          "cost": 2,
          "notes": "V2",
          "maintain": 1,
          "casting time": 1,
          "duration": 0,
        },
        "Lure": {
          "cost": 1,
          "notes": "M137",
          "maintain": None,
          "casting time": 1,
          "duration": 3600,
        },
        "Madness": {
          "cost": None,
          "notes": "M136, cost: 2-6",
          "maintain": 0,
          "casting time": 2,
          "duration": 60,
        },
        "Major Heal": {
          "cost": None,
          "notes": "M91",
          "maintain": None,
          "casting time": 1,
          "duration": 0,    # Permanent -- no need to track
        },
        "Malfunction": {
          "cost": 5,
          "notes": "M177, touch",
          "maintain": 0,
          "casting time": 1,
          "duration": 60,
        },
        "Manastone": {
          "cost": None,
          "notes": "M70",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,    # Indefinite -- no need to track
        },
        "Might": {
          "cost": None,
          "notes": "M37",
          "maintain": None,
          "casting time": 1,
          "duration": 60,
        },
        "Mind-Sending": {
          "cost": 4,
          "notes": "M47",
          "maintain": 4,
          "casting time": 4,
          "duration": 60,
        },
        "Minor Heal": {
          "cost": None,
          "notes": "M91",
          "maintain": None,
          "casting time": 1,
          "duration": 0,    # Permanent -- no need to track
        },
        "Pain": {
          "cost": 2,
          "notes": "M36, vs. HT",
          "maintain": 0,
          "casting time": 1,
          "duration": 1,
        },
        "Panic": {
          "cost": 4,
          "notes": "M134, vs. Will",
          "maintain": 2,
          "casting time": 1,
          "duration": 60,
        },
        "Phase": {
          "cost": 3,
          "notes": "M83, avoid an attack",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Planar Summons": {
          "cost": None,
          "notes": "M82",
          "maintain": 0,
          "casting time": 300,
          "duration": 3600,
        },
        "Powerstone": {
          "cost": 20,
          "notes": "M69",
          "maintain": None,
          "casting time": 1,
          "duration": 0,    # Permanent -- no need to track
        },
        "Relieve Sickness": {
          "cost": 2,
          "notes": "M90",
          "maintain": 2,
          "casting time": 10,
          "duration": 600,  # 10 minutes
        },
        "Repair": {
          "cost": None,
          "notes": "M118",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,    # Permanent -- no need to track
        },
        "Restoration": {
          "cost": 15,
          "notes": "M93",
          "maintain": 0,
          "casting time": 60,
          "duration": 0,    # Permanent -- no need to track
        },
        "Rotting Death": {
          "cost": 3,
          "notes": "M154 vs. HT, needs touch",
          "maintain": 2,
          "casting time": 1,
          "duration": 1,
        },
        "Seek Machine": {
          "cost": 3,
          "notes": "M175",
          "maintain": None,
          "casting time": 10,
          "duration": 0,
        },
        "Seek Plant": {
          "cost": 2,
          "notes": "M161",
          "maintain": None,
          "casting time": 1,
          "duration": 0,
        },
        "Sense Emotion": {
          "cost": 2,
          "notes": "M45",
          "maintain": None,
          "casting time": 1,
          "duration": 0,
        },
        "Sense Foes": {
          "cost": 2,
          "notes": "M45",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Sense Life": {
          "cost": None,
          "notes": "M45, cost 1/2 per yard radius, see M11",
          "maintain": None,
          "casting time": 1,
          "duration": 0,
        },
        "Shapeshifting": {
          "cost": None,
          "notes": "M32",
          "maintain": None,
          "casting time": 3,
          "duration": 3600,
        },
        "Shield": {
          "cost": 2,
          "notes": "M167",
          "maintain": None,
          "casting time": 1,
          "duration": 60,
        },
        "Sleep": {
          "cost": 4,
          "notes": "M135",
          "maintain": 0,
          "casting time": 3,
          "duration": 0,
        },
        "Spasm": {
          "cost": 2,
          "notes": "M35",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Stop Power": {
          "cost": None,
          "notes": "M179, 3 pts /1.5 yard radius",
          "maintain": 0,
          "casting time": 3,
          "duration": 60,
        },
        "Strike Blind": {
          "cost": 4,
          "notes": "M38, vs HT",
          "maintain": 2,
          "casting time": 1,
          "duration": 10,
        },
        "Stun": {
          "cost": 2,
          "notes": "M37, B420, vs. HT",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Summon Demon": {
          "cost": 20,
          "notes": "M155",
          "maintain": 0,
          "casting time": 300,
          "duration": 3600,
        },
        "Summon Spirit": {
          "cost": 20,
          "notes": "M150",
          "maintain": 0,
          "casting time": 300,
          "duration": 60,
        },
        "Teleport": {
          "cost": None,
          "notes": "M147, cost: 5 for 100 yards",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Terror": {
          "cost": 4,
          "notes": "M134, Area, Will negates",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,
        },
        "Tell Time": {
          "cost": 1,
          "notes": "M100",
          "maintain": 2,
          "casting time": 1,
          "duration": 0,
        },
        "Throw Spell": {
          "cost": 3,
          "notes": "M128",
          "maintain": 0,
          "casting time": 1,
          "duration": 0,    # Indefinite -- no need to track
        },
        "Total Paralysis": {
          "cost": None,
          "notes": "M40, cost: 2-6",
          "maintain": 0,
          "casting time": 1,
          "duration": 60,
        },
        "Wall Of Lightning": {
          "cost": None,
          "notes": "M197",
          "maintain": 0,
          "casting time": 1,
          "duration": 60,
        },
        "Wizard Eye": {
          "cost": 4,
          "notes": "M104",
          "maintain": 2,
          "casting time": 2,
          "duration": 60,
        },
        "Zombie": {
          "cost": 8,
          "notes": "M151",
          "maintain": None,
          "casting time": 60,
          "duration": 0,    # Permanent -- no need to track
        }
    }

    # Posture: B551; 'attack' is melee, 'target' is ranged
    posture = {
        'standing':  {'attack':  0, 'defense':  0, 'target':  0},
        'crouching': {'attack': -2, 'defense':  0, 'target': -2},
        'kneeling':  {'attack': -2, 'defense': -2, 'target': -2},
        'crawling':  {'attack': -4, 'defense': -3, 'target': -2},
        'sitting':   {'attack': -2, 'defense': -2, 'target': -2},
        'lying':     {'attack': -4, 'defense': -3, 'target': -2},
    }

    # This is for the Persephone version of the GURPS ruleset.  It's only for
    # color and does not deal with armoring parts of the body or blowthrough
    # or anything that goes with the non-Lite version of GURPS.
    hit_location_table = {3:  'head',
                          4:  'head',
                          5:  'face',
                          6:  'right thigh',
                          7:  'right calf',
                          8:  'right arm',
                          9:  'stomach',
                          10: 'chest/back',
                          11: 'groin/hip/butt',
                          12: 'left arm',
                          13: 'left calf',
                          14: 'left thigh',
                          15: 'hand',
                          16: 'foot',
                          17: 'neck',
                          18: 'neck'}

    (MAJOR_WOUND_SUCCESS,
     MAJOR_WOUND_SIMPLE_FAIL,
     MAJOR_WOUND_BAD_FAIL) = range(3)

    def __init__(self,
                 window_manager  # GmWindowManager object for menus and errors
                 ):
        super(GurpsRuleset, self).__init__(window_manager)

    #
    # Public Methods
    #

    def can_finish_turn(self,
                        fighter  # Fighter object
                        ):
        '''
        If a Fighter has done something this turn, we can move to the next
        Fighter.  Otherwise, the Fighter should do something before we go to
        the next Fighter.

        Returns: <bool> telling the caller whether this Fighter needs to do
        something before we move on.
        '''

        # If the fighter does one of these things and the turn is over, he
        # clearly hasn't forgotten to do something.  Other actions are passive
        # and their existence doesn't mean that the fighter has actually tried
        # to do anything.

        active_actions = [
            'aim',             'all-out-attack', 'attack',
            'cast-spell',      'change-posture', 'concentrate',
            'defend',          'don-armor',      'draw-weapon',
            'evaluate',        'feint',          'move',
            'move-and-attack', 'nothing',        'reload',
            'stun',            'use-item',       'user-defined'
        ]

        for action in fighter.details['actions_this_turn']:
            if action in active_actions:
                return True

        if not fighter.is_conscious():
            return True

        if fighter.timers.is_busy():
            return True

        return False

    def damage_to_string(self,
                         damages  # list of dict -- returned by 'get_damage'.
                                  # The dict looks like:
                                  #
                                  #  {'attack_type': <string> (e.g., 'sw')
                                  #   'num_dice': <int>
                                  #   'plus': <int>
                                  #   'damage_type': <string> (e.g., 'crushing')}
                         ):
        '''
        Converts array of dicts returned by get_damage into a string.

        Returns the string.
        '''
        results = []
        for damage in damages:
            string = []
            if damage['attack_type'] is not None:
                string.append('%s: ' % damage['attack_type'])
            string.append('%dd%+d ' % (damage['num_dice'], damage['plus']))
            string.append('(%s)' % damage['damage_type'])
            results.append(''.join(string))

        return ', '.join(results)

    def end_turn(self,
                 fighter,       # Fighter object
                 fight_handler  # FightHandler object
                 ):
        '''
        Performs all of the stuff required for a Fighter to end his/her
        turn.  Does all the consciousness/death checks, etc.

        Returns: nothing
        '''
        fighter.details['shock'] = 0

        if fighter.details['stunned'] and not fight_handler.world.playing_back:
            stunned_menu = [
                (('Succeeded (roll <= HT (%d))' %
                            fighter.details['current']['ht']), True),
                ('Missed roll', False),]
            recovered_from_stun = self._window_manager.menu(
                        '%s Stunned (B420): Roll <= HT to recover' %
                            fighter.name,
                        stunned_menu)
            if recovered_from_stun:
                self.do_action(fighter,
                               {'action-name': 'stun', 'stun': False},
                               fight_handler)

    def get_action_menu(self,
                        fighter,    # Fighter object
                        opponent    # Fighter object
                        ):
        '''
        Builds a list of all of the things that this fighter can do this
        round.  This list will be fed to GmWindowManager.menu(), so each
        element is a tuple of

        1) the string to be displayed
        2) a dict that contains one or more of

            'text' - text to go in a timer to show what the Fighter is doing
            'action' - an action to be sent to the ruleset
            'menu' - a menu to be recursively called

        NOTE: all menu items should end, ultimately, in an 'action' because
        then the activity will be logged in the history and can be played-back
        if there's a bug to be reported.

        Returns the menu (i.e., the list)
        '''

        action_menu = []

        if fighter.details['stunned']:
            # TODO: not quite sure how to handle this one for playback
            action_menu.append(
                ('do nothing (stunned)', {'text': ['Do Nothing (Stunned)',
                                                   ' Defense: any @-4',
                                                   ' Move: none'],
                                          'action': {'action-name': 'nothing'}}
                )
            )
            return action_menu  # No other actions permitted


        # Figure out who we are and what we're holding.

        weapon, weapon_index = fighter.get_current_weapon()
        holding_ranged = (False if weapon is None else
                                (weapon['type'] == 'ranged weapon'))


        # Posture SUB-menu

        posture_menu = []
        for posture in GurpsRuleset.posture.iterkeys():
            if posture != fighter.details['posture']:
                posture_menu.append((posture,
                                     {'action': {'action-name': 'change-posture',
                                      'posture': posture}}
                                   ))


        # Build the action_menu.  Alphabetical order.  Only allow the things
        # the fighter can do based on zis current situation.

        if holding_ranged:
            if weapon['ammo']['shots_left'] > 0:

                # Aim
                #
                # Ask if we're bracing if this is the first round of aiming
                # B364 (NOTE: Combat Lite on B234 doesn't mention bracing).
                if fighter.details['aim']['rounds'] == 0:
                    brace_menu = [
                        ('Bracing (B364)', {'action': {'action-name': 'aim',
                                                       'braced': True}
                                           }),
                        ('Not Bracing', {'action': {'action-name': 'aim',
                                                    'braced': False}})
                    ]
                    action_menu.append(('Aim (B324, B364)',
                                        {'menu': brace_menu}))
                else:
                    action_menu.append(('Aim (B324, B364)',
                                        {'action': {'action-name': 'aim',
                                                    'braced': False}}))


        action_menu.extend([
            ('posture (B551)',         {'menu': posture_menu}),
            ('Concentrate (B366)',     {'action': {'action-name': 'concentrate'}}),
            ('Defense, all out',       {'action': {'action-name': 'defend'}}),
        ])

        # Spell casters.

        if 'spells' in fighter.details:
            spell_menu = []
            for index, spell in enumerate(fighter.details['spells']):
                if spell['name'] not in GurpsRuleset.spells:
                    self._window_manager.error(
                        ['Spell "%s" not in GurpsRuleset.spells' %
                                                                spell['name']]
                    )
                    continue
                complete_spell = copy.deepcopy(spell)
                complete_spell.update(GurpsRuleset.spells[spell['name']])

                cast_text_array = ['%s -' % complete_spell['name']]

                for piece in ['cost',
                              'skill',
                              'casting time',
                              'duration',
                              'notes']:
                    if piece in complete_spell:
                        cast_text_array.append('%s:%r' % (piece,
                                                         complete_spell[piece]))
                cast_text = ' '.join(cast_text_array)
                spell_menu.append(
                    (cast_text,
                    {'action': {'action-name': 'cast-spell', 'spell-index': index}
                    }))
            spell_menu = sorted(spell_menu, key=lambda x: x[0].upper())

            action_menu.append(('cast Spell', {'menu': spell_menu}))


        action_menu.append(('evaluate (B364)', {'action': {'action-name': 'evaluate'}}
                          ))

        # Can only feint with a melee weapon
        if weapon is not None and holding_ranged == False:
            action_menu.append(('feint (B365)', {'action': {'action-name': 'feint'}}))

        # FP: B426
        move = fighter.details['current']['basic-move']
        if (fighter.details['current']['fp'] <
                        (fighter.details['permanent']['fp'] / 3)):
            move_string = 'half=%d (FP:B426)' % (move/2)
        else:
            move_string = 'full=%d' % move


        action_menu.extend([
            ('move (B364) %s' % move_string,
                                       {'action': {'action-name': 'move'}}),
            ('Move and attack (B365)', {'action': {'action-name': 'move-and-attack'}}),
            ('nothing',                {'action': {'action-name': 'nothing'}}),
        ])

        super(GurpsRuleset, self).get_action_menu(action_menu,
                                                  fighter,
                                                  opponent)

        action_menu = sorted(action_menu, key=lambda x: x[0].upper())
        return action_menu

    def get_block_skill(self,                       # Public to aid in testing.
                        fighter,    # Fighter object
                        weapon      # dict
                        ):
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully block an
               attack
            2) a string describing the calculations that went into the number
        '''
        if weapon is None or weapon['skill'] not in fighter.details['skills']:
            return None, None
        skill = fighter.details['skills'][weapon['skill']]
        block_why = []
        block_skill_modified = False

        block_skill = 3 + int(skill * 0.5)
        block_why.append('Block (B327, B375) w/%s @ (skill(%d)/2)+3 = %d' % (
                                                                weapon['name'],
                                                                skill,
                                                                block_skill))

        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.details['advantages']:
            block_skill_modified = True
            block_why.append('  +1 due to combat reflexes (B43)')
            block_skill += 1

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            block_skill_modified = True
            block_skill += posture_mods['defense']
            block_why.append('  %+d due to %s posture' %
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))

        if block_skill_modified:
            block_why.append('  ...for a block skill total = %d' % block_skill)

        return block_skill, block_why

    def get_character_description(self,
                                  character,   # Fighter object
                                  output,      # recepticle for character data.
                                               # [[{'text','mode'},...], #line 0
                                               #  [...],               ] #line 1
                                  ):
        '''
        Provides a text description of a Fighter including all of the
        attributes (current and permanent), equipment, skills, etc.

        Portions of the character description are ruleset-specific.  That's
        why this routine is in GurpsRuleset rather than in the Fighter class.

        Returns: nothing.  The output is written to the |output| variable.
        '''

        # attributes

        mode = curses.A_NORMAL
        output.append([{'text': 'Attributes', 'mode': mode | curses.A_BOLD}])
        found_one = False
        pieces = []

        first_row = ['st', 'dx', 'iq', 'ht', 'per']
        first_row_pieces = {}
        for row in range(2):
            found_one_this_row = False
            for item_key in character.details['permanent'].iterkeys():
                in_first_row = item_key in first_row
                if row == 0 and not in_first_row:
                    continue
                if row != 0 and in_first_row:
                    continue
                text = '%s:%d/%d' % (item_key,
                                     character.details['current'][item_key],
                                     character.details['permanent'][item_key])
                if (character.details['current'][item_key] ==
                                     character.details['permanent'][item_key]):
                    mode = curses.A_NORMAL
                else:
                    mode = (curses.color_pair(
                                ca_gui.GmWindowManager.YELLOW_BLACK) |
                                    curses.A_BOLD)

                if row == 0:
                    # Save the first row as pieces so we can put them in the
                    # proper order, later.
                    first_row_pieces[item_key] = {'text': '%s ' % text,
                                                  'mode': mode}
                else:
                    pieces.append({'text': '%s ' % text, 'mode': mode})
                found_one = True
                found_one_this_row = True

            if found_one_this_row:
                if row == 0:
                    for item_key in first_row:
                        pieces.append(first_row_pieces[item_key])

                pieces.insert(0, {'text': '  ', 'mode': curses.A_NORMAL})
                output.append(copy.deepcopy(pieces))
                del pieces[:]

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # stuff

        mode = curses.A_NORMAL
        output.append([{'text': 'Equipment', 'mode': mode | curses.A_BOLD}])

        in_use_items = []
        armor_in_use, throw_away = character.get_current_armor()
        if armor_in_use is not None:
            in_use_items.append(armor_in_use)
        weapon_in_use, throw_away = character.get_current_weapon()
        if weapon_in_use is not None:
            in_use_items.append(weapon_in_use)

        found_one = False
        for item in sorted(character.details['stuff'],
                           key=lambda x: x['name']):
            found_one = True
            ca_equipment.EquipmentManager.get_description(item,
                                                          in_use_items,
                                                          output)

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # advantages

        mode = curses.A_NORMAL
        output.append([{'text': 'Advantages', 'mode': mode | curses.A_BOLD}])

        found_one = False
        for advantage, value in sorted(
                                    character.details['advantages'].iteritems(),
                                    key=lambda (k,v): (k, v)):
            found_one = True
            output.append([{'text': '  %s: %r' % (advantage, value),
                            'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # skills

        mode = curses.A_NORMAL
        output.append([{'text': 'Skills', 'mode': mode | curses.A_BOLD}])

        found_one = False
        for skill, value in sorted(character.details['skills'].iteritems(),
                                   key=lambda (k,v): (k,v)):
            found_one = True
            output.append([{'text': '  %s: %d' % (skill, value),
                            'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # spells

        if 'spells' in character.details:
            mode = curses.A_NORMAL
            output.append([{'text': 'Spells', 'mode': mode | curses.A_BOLD}])

            found_one = False
            for spell in sorted(character.details['spells'],
                                key=lambda(x): x['name']):
                if spell['name'] not in GurpsRuleset.spells:
                    self._window_manager.error(
                        ['Spell "%s" not in GurpsRuleset.spells' %
                                                                spell['name']]
                    )
                    continue
                complete_spell = copy.deepcopy(spell)
                complete_spell.update(GurpsRuleset.spells[spell['name']])
                found_one = True
                output.append(
                        [{'text': '  %s (%d): %s' % (complete_spell['name'],
                                                     complete_spell['skill'],
                                                     complete_spell['notes']),
                          'mode': mode}])

            if not found_one:
                output.append([{'text': '  (None)', 'mode': mode}])

        # timers

        mode = curses.A_NORMAL
        output.append([{'text': 'Timers', 'mode': mode | curses.A_BOLD}])

        found_one = False
        timers = character.timers.get_all()  # objects
        for timer in timers:
            found_one = True
            text = timer.get_description()
            leader = '  '
            for line in text:
                output.append([{'text': '%s%s' % (leader, line),
                                'mode': mode}])
                leader = '    '

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

        # notes

        mode = curses.A_NORMAL
        output.append([{'text': 'Notes', 'mode': mode | curses.A_BOLD}])

        found_one = False
        if 'notes' in character.details:
            for note in character.details['notes']:
                found_one = True
                output.append([{'text': '  %s' % note, 'mode': mode}])

        if not found_one:
            output.append([{'text': '  (None)', 'mode': mode}])

    def get_creature_abilities(self):
        '''
        Returns the list of capabilities that, according to the ruleset, a
        creature can have.  See |GurpsRuleset.abilities|
        '''
        return GurpsRuleset.abilities

    def get_damage(self,
                   fighter,   # Fighter object
                   weapon     # dict {'type': 'imp', 'thr': +1, ...}
                   ):
        '''
        Returns a tuple of:
            1) A list of dict describing the kind of damage that |fighter|
               can do with |weapon|.  A weapon can do multiple types of damage
               (for instance a sword can do swinging damage or thrust damage).
               Each type of damage looks like this:

                {'attack_type': <string> (e.g., 'sw')
                 'num_dice': <int>
                 'plus': <int>
                 'damage_type': <string> (e.g., 'crushing')}

            2) a string describing the calculations that went into the pieces
               of the dict
        '''
        st = fighter.details['current']['st']
        results = []
        why = []

        if 'dice' in weapon['damage']:
            damage_type_str = self.__get_damage_type_str(
                                            weapon['damage']['dice']['type'])
            results.append(
                {'attack_type': None,
                 'num_dice': weapon['damage']['dice']['num_dice'],
                 'plus': weapon['damage']['dice']['plus'],
                 'damage_type': damage_type_str})
            why.append('Weapon %s Damage: %dd%+d' % (
                                          weapon['name'],
                                          weapon['damage']['dice']['num_dice'],
                                          weapon['damage']['dice']['plus']))
        if 'sw' in weapon['damage']:
            damage_type_str = self.__get_damage_type_str(
                                            weapon['damage']['sw']['type'])
            results.append(
                {'attack_type': 'sw',
                 'num_dice': GurpsRuleset.melee_damage[st]['sw']['num_dice'],
                 'plus': GurpsRuleset.melee_damage[st]['sw']['plus'] +
                                            weapon['damage']['sw']['plus'],
                 'damage_type': damage_type_str})

            why.append('Weapon %s Damage: sw%+d' % (
                                             weapon['name'],
                                             weapon['damage']['sw']['plus']))
            why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                       (st,
                        GurpsRuleset.melee_damage[st]['sw']['num_dice'],
                        GurpsRuleset.melee_damage[st]['sw']['plus']))
            if weapon['damage']['sw']['plus'] != 0:
                why.append('  ...%+d for the weapon' %
                                            weapon['damage']['sw']['plus'])
            why.append('  ...damage: %dd%+d' %
                (GurpsRuleset.melee_damage[st]['sw']['num_dice'],
                 GurpsRuleset.melee_damage[st]['sw']['plus'] +
                                            weapon['damage']['sw']['plus']))

        if 'thr' in weapon['damage']:
            damage_type_str = self.__get_damage_type_str(
                                            weapon['damage']['thr']['type'])
            results.append(
                {'attack_type': 'thr',
                 'num_dice': GurpsRuleset.melee_damage[st]['thr']['num_dice'],
                 'plus': GurpsRuleset.melee_damage[st]['thr']['plus'] +
                                            weapon['damage']['thr']['plus'],
                 'damage_type': damage_type_str})

            why.append('Weapon %s Damage: thr%+d' % (
                                            weapon['name'],
                                            weapon['damage']['thr']['plus']))
            why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                            (st,
                             GurpsRuleset.melee_damage[st]['thr']['num_dice'],
                             GurpsRuleset.melee_damage[st]['thr']['plus']))
            if weapon['damage']['thr']['plus'] != 0:
                why.append('  ...%+d for the weapon' %
                                            weapon['damage']['thr']['plus'])
            why.append('  ...damage: %dd%+d' %
                (GurpsRuleset.melee_damage[st]['thr']['num_dice'],
                 GurpsRuleset.melee_damage[st]['thr']['plus'] +
                                            weapon['damage']['thr']['plus']))

        if len(results) == 0:
            return '(None)', why

        return results, why

    def get_dodge_skill(self,                       # Public to aid in testing
                        fighter  # Fighter object
                        ):  # B326
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully dodge an
               attack
            2) a string describing the calculations that went into the number
        '''
        dodge_why = []
        dodge_skill_modified = False

        dodge_skill = 3 + int(fighter.details['current']['basic-speed'])
        dodge_why.append('Dodge (B326) @ int(basic-speed(%.1f))+3 = %d' % (
                                fighter.details['current']['basic-speed'],
                                dodge_skill))

        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.details['advantages']:  # B43
            dodge_skill_modified = True
            dodge_why.append('  +1 due to combat reflexes (B43)')
            dodge_skill += 1

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            dodge_skill_modified = True
            dodge_skill += posture_mods['defense']
            dodge_why.append('  %+d due to %s posture' %
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))

        # B327
        if (fighter.details['current']['hp'] <
                                    fighter.details['permanent']['hp']/3.0):
            dodge_skill_modified = True
            dodge_why.append(
                '  dodge(%d)/2 (round up) due to hp(%d) < perm-hp(%d)/3 (B327)'
                                    % (dodge_skill,
                                       fighter.details['current']['hp'],
                                       fighter.details['permanent']['hp']))
            dodge_skill = int(((dodge_skill)/2.0) + 0.5)

        # B426
        if (fighter.details['current']['fp'] <
                                    fighter.details['permanent']['fp']/3.0):
            dodge_skill_modified = True
            dodge_why.append(
                '  dodge(%d)/2 (round up) due to fp(%d) < perm-fp(%d)/3 (B426)'
                                    % (dodge_skill,
                                       fighter.details['current']['fp'],
                                       fighter.details['permanent']['fp']))
            dodge_skill = int(((dodge_skill)/2.0) + 0.5)

        if dodge_skill_modified:
            dodge_why.append('  ...for a dodge skill total = %d' % dodge_skill)

        return dodge_skill, dodge_why

    def get_fight_commands(self,
                           fight_handler    # FightHandler object
                           ):
        '''
        Returns fight commands that are specific to the GURPS ruleset.  These
        commands are structured for a command ribbon.  The functions point
        right back to local functions of the GurpsRuleset.
        '''
        return {
            ord('f'): {'name': 'FP damage',
                       'func': self.__damage_FP,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                       'help': 'Removes fatigue points from the currently ' +
                               'selected fighter, or the current opponent ' +
                               '(if nobody is selected), or (if neither ' +
                               'of those) the ' +
                               'fighter that currently has the initiative. ',
                      },
            ord('S'): {'name': 'Stun',
                       'func': self.__stun,
                       'param': {
                            'view': None,
                            'current-opponent': None,
                            'current': None,
                            'fight_handler': fight_handler
                       },
                       'show': True,
                       'help': 'Causes the selected fighter to be ' +
                               'stunned (GURPS B420)',
                      },
            }

    def get_fighter_defenses_notes(self,
                                   fighter,  # Fighter object
                                   opponent  # Fighter object
                                   ):
        '''
        Returns a tuple of strings describing:

        1) the current (based on weapons held, armor worn, etc) defensive
           capability (parry, dodge, block) of the Fighter, and
        2) the pieces that went into the above calculations
        '''
        notes = []
        why = []

        weapon, holding_weapon_index = fighter.get_current_weapon()
        unarmed_skills = self.get_weapons_unarmed_skills(weapon)

        unarmed_info = None
        if unarmed_skills is not None:
            unarmed_info = self.get_unarmed_info(fighter,
                                                 opponent,
                                                 weapon,
                                                 unarmed_skills)

        dodge_skill, dodge_why = self.get_dodge_skill(fighter)
        if dodge_skill is not None:
            dodge_string = 'Dodge (B326): %d' % dodge_skill
            why.extend(dodge_why)
            notes.append(dodge_string)

        if unarmed_skills is not None:  # Unarmed Parry
            notes.append('%s: %d' % (unarmed_info['parry_string'],
                                     unarmed_info['parry_skill']))

        elif weapon['type'] == 'shield':  # NOTE: cloaks also have this 'type'
            block_skill, block_why = self.get_block_skill(fighter, weapon)
            if block_skill is not None:
                why.extend(block_why)
                notes.append('Block (B327, B375): %d' % block_skill)

        elif weapon['type'] == 'melee weapon':
            parry_skill, parry_why = self.get_parry_skill(fighter, weapon)
            if parry_skill is not None:
                why.extend(parry_why)
                notes.append('Parry (B327, B376): %d' % parry_skill)

        # Armor


        dr = 0
        dr_text_array = []
        armor, armor_index = fighter.get_current_armor()
        if armor is not None:
            dr += armor['dr']
            dr_text_array.append(armor['name'])

        if 'Damage Resistance' in fighter.details['advantages']:
            # GURPS rules, B46, 5 points per level of DR advantage
            dr += (fighter.details['advantages']['Damage Resistance']/5)
            dr_text_array.append('DR Advantage')

        dr_text = ' + '.join(dr_text_array)

        if dr > 0:
            notes.append('Armor: "%s", DR: %d' % (dr_text, dr))
            why.append('Armor: "%s", DR: %d' % (dr_text, dr))
            if (armor is not None and 'notes' in armor and
                                                    len(armor['notes']) != 0):
                why.append('  %s' % armor['notes'])


        return notes, why

    def get_fighter_notes(self,
                          fighter   # Fighter object
                          ):
        '''
        Returns a list of strings describing the current fighting state of the
        fighter (rounds available, whether s/he's aiming, current posture,
        etc.)
        '''
        notes = []

        # Ranged weapon status

        weapon, holding_weapon_index = fighter.get_current_weapon()
        if holding_weapon_index is not None:
            if weapon['type'] == 'ranged weapon':
                clip_name = weapon['ammo']['name']
                clip = None
                for item in fighter.details['stuff']:
                    if item['name'] == clip_name:
                        clip = item
                        break

                notes.append('  %d/%d shots, %d reloads' % (
                                    weapon['ammo']['shots_left'],
                                    weapon['ammo']['shots'],
                                    (0 if clip is None else clip['count'])))

        # Active aim

        if (fighter.details['aim'] is not None and
                                    fighter.details['aim']['rounds'] != 0):
            notes.append('Aiming')

        # And, now, off to the regular stuff

        if fighter.details['posture'] != 'standing':
            notes.append('Posture: %s' % fighter.details['posture'])
        if fighter.details['shock'] != 0:
            notes.append('DX and IQ are at %d (shock)' %
                                                    fighter.details['shock'])

        if (fighter.details['current']['hp'] <
                                    fighter.details['permanent']['hp']/3.0):
            # Already incorporated into Dodge
            notes.append('Dodge/Move are at 1/2')

        return notes

    def get_fighter_to_hit_damage_notes(self,
                                        fighter,    # Fighter object
                                        opponent    # Fighter object
                                        ):
        '''
        Returns a list of strings describing the current (using the current
        weapon, in the current posture, etc.) fighting capability (to-hit and
        damage) of the fighter.
        '''
        notes = []
        weapon, holding_weapon_index = fighter.get_current_weapon()
        unarmed_skills = self.get_weapons_unarmed_skills(weapon)

        if weapon is not None:
            notes.append('%s' % weapon['name'])

        if unarmed_skills is None:
            if weapon['skill'] in fighter.details['skills']:
                to_hit, ignore_why = self.get_to_hit(fighter, opponent, weapon)
                if to_hit is None:
                    self._window_manager.error(
                        ['%s requires "%s" skill not had by "%s"' %
                                                             (weapon['name'],
                                                              weapon['skill'],
                                                              fighter.name)])
                else:
                    damage, ignore_why = self.get_damage(fighter, weapon)
                    damage_str = self.damage_to_string(damage)
                    notes.append('  to-hit: %d' % to_hit)
                    notes.append('  damage: %s' % damage_str)
            else:
                self._window_manager.error(
                    ['%s requires "%s" skill not had by "%s"' %
                                                             (weapon['name'],
                                                              weapon['skill'],
                                                              fighter.name)])
        else:
            unarmed_info = self.get_unarmed_info(fighter,
                                                 opponent,
                                                 weapon,
                                                 unarmed_skills)

            notes.append(unarmed_info['punch_string'])
            notes.append('  to-hit: %d, damage: %s' % (
                                                unarmed_info['punch_skill'],
                                                unarmed_info['punch_damage']))

            notes.append(unarmed_info['kick_string'])
            notes.append('  to-hit: %d, damage: %s' % (
                                                unarmed_info['kick_skill'],
                                                unarmed_info['kick_damage']))

        return notes

    def get_parry_skill(self,                       # Public to aid in testing
                        fighter,    # Fighter object
                        weapon      # dict
                        ):
        '''
        Returns a tuple of:
            1) the number the defender needs to roll to successfully parry an
               attack
            2) a string describing the calculations that went into the number
        '''
        if weapon is None or weapon['skill'] not in fighter.details['skills']:
            return None, None
        skill = fighter.details['skills'][weapon['skill']]
        parry_why = []
        parry_skill_modified = False

        parry_skill = 3 + int(skill * 0.5)
        parry_why.append('Parry (B327, B376) w/%s @ (skill(%d)/2)+3 = %d' % (
                                                                weapon['name'],
                                                                skill,
                                                                parry_skill))

        if fighter.details['stunned']:
            dodge_skill -= 4
            dodge_why.append('  -4 due to being stunned (B420)')

        if 'parry' in weapon:
            parry_skill += weapon['parry']
            parry_skill_modified = True
            parry_why.append('  %+d due to weapon modifiers' % weapon['parry'])

        if 'Combat Reflexes' in fighter.details['advantages']:
            parry_skill_modified = True
            parry_why.append('  +1 due to combat reflexes (B43)')
            parry_skill += 1

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['defense'] != 0:
            parry_skill_modified = True
            parry_skill += posture_mods['defense']
            parry_why.append('  %+d due to %s posture' %
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))
        if parry_skill_modified:
            parry_why.append('  ...for a parry skill total = %d' % parry_skill)

        return parry_skill, parry_why

    def get_posture_mods(self,
                         posture    # string: 'standing' | ...
                         ):
        '''
        Returns a dict with the attack, defense, and target minuses for the
        given posture.
        '''
        return (None if posture not in GurpsRuleset.posture else
                                            GurpsRuleset.posture[posture])

    def get_sample_items(self):
        '''
        Returns a list of sample equipment for creating new game files.
        '''
        return [
            {
                "count": 1,
                "notes": "1d for HT+1d hrs unless other healing",
                "type": "misc",
                "owners": None,
                "name": "Patch: light heal"
            },
            {
              "count": 1,
              "owners": [],
              "name": "Armor, Light Street",
              "type": "armor",
              "notes": "Some combination of ballistic, ablative, and disruptor.",
              "dr": 3
            },
            {
                "count": 1,
                "owners": [],
                "name": "Tonfa",
                "notes": "",
                "damage": { "sw": { "type": "cr", "plus": 0 },
                            "thr": { "type": "cr", "plus": 1 } },
                "parry": 0,
                "skill": "Tonfa",
                "type": "melee weapon"
            },
            {
                "acc": 2,
                "count": 1,
                "owners": None,
                "name": "pistol, Baretta DX 192",
                "notes": "",
                "damage": {
                    "dice": { "plus": 4, "num_dice": 1, "type": "pi" }
                },
                "reload": 3,
                "skill": "Beam Weapons (Pistol)",
                "type": "ranged weapon",
                "ammo": { "name": "C Cell", "shots": 8, "shots_left": 8 }
            },
            {
                "count": 1,
                "notes": "",
                "type": "misc",
                "owners": None,
                "name": "C Cell"
            }
        ]

    def get_sections_in_template(self):
        '''
        This returns an array of the Fighter section headings that are
        expected (well, not _expected_ but any headings that aren't in this
        list should probably not be there) to be in a template.
        '''
        sections = ['skills', 'advantages', 'spells']
        sections.extend(super(GurpsRuleset, self).get_sections_in_template())

        # Transitory sections, not used in template:
        #   aim, stunned, shock, posture, check_for_death,
        #   actions_this_turn,

        return sections

    def get_to_hit(self,
                   fighter,     # Fighter object
                   opponent,    # Fighter object
                   weapon
                   ):
        '''
        Returns tuple (skill, why) where:
            'skill' (number) is the value the attacker needs to roll to-hit
                    the target.
            'why'   is an array of strings describing why the to-hit numbers
                    are what they are.
        '''
        # TODO: need convenient defaults -- maybe as an entry to the skill
        if weapon['skill'] not in fighter.details['skills']:
            return None, None

        why = []
        skill = fighter.details['skills'][weapon['skill']]
        why.append('Weapon %s w/skill = %d' % (weapon['name'], skill))

        if 'acc' in weapon:
            if fighter.details['aim']['rounds'] > 0:
                why.append('  +%d due to aiming for 1' % weapon['acc'])
                skill += weapon['acc']
                if fighter.details['aim']['braced']:
                    why.append('  +1 due to bracing')
                    skill += 1
            if fighter.details['aim']['rounds'] == 2:
                why.append('  +1 due to one more round of aiming')
                skill += 1

            elif fighter.details['aim']['rounds'] > 2:
                why.append('  +2 due to 2 or more additional rounds of aiming')
                skill += 2

        # Shock

        if fighter.details['shock'] != 0:
            why.append('  %+d due to shock' % fighter.details['shock'])
            skill += fighter.details['shock']

        # Posture

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['attack'] != 0:
            if weapon['type'] == 'melee weapon':
                why.append('  %+d due %s posture' % (
                        posture_mods['attack'], fighter.details['posture']))
                skill += posture_mods['attack']
            else:
                why.append('  NOTE: %s posture doesn\'t matter for ranged' %
                                                    fighter.details['posture'])
                why.append('    attacks (B551).')

        # Opponent's posture

        if opponent is not None:
            opponent_posture_mods = self.get_posture_mods(
                                                opponent.details['posture'])
            if opponent_posture_mods is not None:
                if weapon['type'] == 'ranged weapon':
                    skill += opponent_posture_mods['target']
                    why.append('  %+d for opponent\'s %s posture' %
                                        (opponent_posture_mods['target'],
                                         opponent.details['posture']))


        why.append('  ...for a to-hit total of %d' % skill)
        return skill, why

    def get_unarmed_info(self,
                         fighter,        # Fighter object
                         opponent,       # Fighter object
                         weapon,         # None or dict.  May be brass knuckles.
                         unarmed_skills  # [string, string, ...]
                         ):
        '''
        Makes sense of the cascade of unarmed skills (brawling, boxing,
        karate).  Takes into account posture and other states to determine
        to-hit and damage for hand-to-hand and kicking.

        Returns: dict with all the information
          {
            'punch_skill': <int> number the attacker needs to hit the target
                                 while punching (for best of DX, brawling, etc.)
            'punch_string': <string> describing amount and type of damage
            'punch_damage': <dict> {'num_dice': <int>, 'plus': <int>}

            'kick_skill': <int> number the attacker needs to hit the target
                                while kicking (for best of DX, boxing, etc.)
            'kick_string': <string> describing amount and type of damage
            'kick_damage': <dict> {'num_dice': <int>, 'plus': <int>}

            'parry_skill': <int> number the defender needs to parry an attack
                                 (for best of DX, brawling, etc.)
            'parry_string': <string> describing type of parry

            'why': [] strings describing how each of the above values were
                      determined
          }
        '''

        # Assumes 'dx' is in unarmed_skills
        result = {
            'punch_skill': fighter.details['current']['dx'],
            'punch_string': 'Punch (DX) (B271, B370)',
            'punch_damage': None,   # String: nd+m

            'kick_skill': 0,
            'kick_string': 'Kick (DX-2) (B271, B370)',
            'kick_damage': None,    # String: nd+m

            'parry_skill': fighter.details['current']['dx'],
            'parry_string': 'Unarmed Parry (B376)',

            'why': []
        }

        # Using separate arrays so that I can print them out in a different
        # order than I calculate them.
        punch_why = []
        punch_damage_why = []
        kick_why = []
        kick_damage_why = []
        parry_why = []

        plus_per_die_of_thrust = 0
        plus_per_die_of_thrust_string = None

        # boxing, brawling, karate, dx
        if ('Brawling' in fighter.details['skills'] and
                                                'Brawling' in unarmed_skills):
            if result['punch_skill'] <= fighter.details['skills']['Brawling']:
                result['punch_string'] = 'Brawling Punch (B182, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['Brawling']
                result['kick_string'] = 'Brawling Kick (B182, B271, B370)'
                # Brawling: @DX+2 = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.details['current']['dx']+2:
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Brawling(%d) @DX(%d)+2 = +1/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
            if result['parry_skill'] <= fighter.details['skills']['Brawling']:
                result['parry_skill'] = fighter.details['skills']['Brawling']
                result['parry_string'] = 'Brawling Parry (B182, B376)'
        if ('karate' in fighter.details['skills'] and
                                                'karate' in unarmed_skills):
            if result['punch_skill'] <= fighter.details['skills']['Karate']:
                result['punch_string'] = 'Karate Punch (B203, B271, B370)'
                result['kick_string'] = 'Karate Kick (B203, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['Karate']
                # Karate: @DX+1+ = +2 per die of thrusting damage
                # Karate: @DX = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.details['current']['dx']+1:
                    plus_per_die_of_thrust = 2
                    plus_per_die_of_thrust_string = (
                        'Karate(%d) @DX(%d)+1 = +2/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                elif result['punch_skill'] >= fighter.details['current']['dx']:
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Karate(%d) @DX(%d) = +1/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                else:
                    plus_per_die_of_thrust = 0
                    plus_per_die_of_thrust_string = None
            if result['parry_skill'] <= fighter.details['skills']['Karate']:
                result['parry_skill'] = fighter.details['skills']['Karate']
                result['parry_string'] = 'Karate Parry (B203, B376)'

        # (brawling, karate, dx) - 2
        result['kick_skill'] = result['punch_skill'] - 2
        kick_why.append('%s = %s (%d) -2 = to-hit: %d' % (
                                                    result['kick_string'],
                                                    result['punch_string'],
                                                    result['punch_skill'],
                                                    result['kick_skill']))

        if ('boxing' in fighter.details['skills'] and
                                                'boxing' in unarmed_skills):
            # TODO: if skills are equal, boxing should be used in favor of
            # brawling or DX but NOT in favor of karate.  It's placed here
            # because the kick skill isn't improved by boxing.
            if result['punch_skill'] < fighter.details['skills']['Boxing']:
                result['punch_string'] = 'Boxing Punch (B182, B271, B370)'
                result['punch_skill'] = fighter.details['skills']['Boxing']
                # Boxing: @DX+2+ = +2 per die of thrusting damage
                # Boxing: @DX+1 = +1 per die of thrusting damage
                if result['punch_skill'] >= fighter.details['current']['dx']+2:
                    plus_per_die_of_thrust = 2
                    plus_per_die_of_thrust_string = (
                        'Boxing(%d) @DX(%d)+2 = +2/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                elif (result['punch_skill'] >=
                                        fighter.details['current']['dx']+1):
                    plus_per_die_of_thrust = 1
                    plus_per_die_of_thrust_string = (
                        'Boxing(%d) @DX(%d)+1 = +1/die of thrusting damage' %
                            (result['punch_skill'],
                             fighter.details['current']['dx']))
                else:
                    plus_per_die_of_thrust = 0
                    plus_per_die_of_thrust_string = None
            if result['parry_skill'] < fighter.details['skills']['Boxing']:
                result['parry_skill'] = fighter.details['skills']['Boxing']
                result['parry_string'] = 'Boxing Parry (B182, B376)'

        punch_why.append('%s, to-hit: %d' % (result['punch_string'],
                                             result['punch_skill']))

        # Shock

        if fighter.details['shock'] != 0:
            result['punch_skill'] += fighter.details['shock']
            result['kick_skill'] += fighter.details['shock']

            punch_why.append('  %+d due to shock' % fighter.details['shock'])
            kick_why.append('  %+d due to shock' % fighter.details['shock'])

        # Posture

        posture_mods = self.get_posture_mods(fighter.details['posture'])
        if posture_mods is not None and posture_mods['attack'] != 0:
            result['punch_skill'] += posture_mods['attack']
            result['kick_skill'] += posture_mods['attack']

            punch_why.append('  %+d due to %s posture' %
                                                (posture_mods['attack'],
                                                 fighter.details['posture']))
            kick_why.append('  %+d due to %s posture' %
                                                (posture_mods['attack'],
                                                 fighter.details['posture']))

        # Opponent's posture only for ranged attacks -- not used, here

        parry_raw = result['parry_skill']
        parry_damage_modified = False

        # Brawling, Boxing, Karate, DX: Parry int(skill/2) + 3
        result['parry_skill'] = 3 + int(result['parry_skill']/2)
        parry_why.append('%s @ (punch(%d)/2)+3 = %d' % (result['parry_string'],
                                                        parry_raw,
                                                        result['parry_skill']))
        # Stunned
        if fighter.details['stunned']:
            result['parry_skill'] -= 4
            parry_why.append('  -4 due to being stunned (B420)')

        if 'Combat Reflexes' in fighter.details['advantages']:
            parry_damage_modified = True
            result['parry_skill'] += 1
            parry_why.append('  +1 due to combat reflexes (B43)')

        if posture_mods is not None and posture_mods['defense'] != 0:
            result['parry_skill'] += posture_mods['defense']

            parry_why.append('  %+d due to %s posture' %
                                                (posture_mods['defense'],
                                                 fighter.details['posture']))

        # Final 'why' results

        if parry_damage_modified:
            parry_why.append('  ...for a parry total = %d' %
                                                        result['parry_skill'])
        punch_why.append('  ...for a punch total = %d' % result['punch_skill'])
        kick_why.append('  ...for a kick total = %d' % result['kick_skill'])

        # Damage

        punch_damage = None  # Expressed as dice
        kick_damage = None   # Expressed as dice
        st = fighter.details['current']['st']

        # Base damage

        kick_damage_why.append('Kick damage(B271)=thr')

        damage_modified = False
        kick_damage = copy.deepcopy(GurpsRuleset.melee_damage[st]['thr'])
        kick_damage_why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                                            (st,
                                             kick_damage['num_dice'],
                                             kick_damage['plus']))

        # TODO: maybe I want to make everything use damage_array instead of
        # making it a special case for brass knuckles.
        damage_array = None
        if weapon is None:
            punch_damage = copy.deepcopy(GurpsRuleset.melee_damage[st]['thr'])
            punch_damage_why.append('Punch damage(B271) = thr-1')
            punch_damage_why.append('  plug ST(%d) into table on B16 = %dd%+d' %
                                                (st,
                                                 punch_damage['num_dice'],
                                                 punch_damage['plus']))
            punch_damage['plus'] -= 1
            punch_damage_why.append('  -1 (damage is thr-1) = %dd%+d' %
                                                (punch_damage['num_dice'],
                                                 punch_damage['plus']))
        else:
            damage_array, why = self.get_damage(fighter, weapon)
            punch_damage_why.extend(why)

        # Plusses to damage

        if plus_per_die_of_thrust != 0:
            damage_modified = True
            kick_damage['plus'] += (kick_damage['num_dice'] *
                                    plus_per_die_of_thrust)
            kick_damage_why.append('  %+d/die due to %s' % (
                                                plus_per_die_of_thrust,
                                                plus_per_die_of_thrust_string))
            if damage_array is not None:
                for damage in damage_array:
                    if damage['attack_type'] == 'thr':
                        damage['plus'] += (damage['num_dice'] *
                                                 plus_per_die_of_thrust)
            else:
                punch_damage['plus'] += (punch_damage['num_dice'] *
                                         plus_per_die_of_thrust)

            punch_damage_why.append('  %+d/die of thrust due to %s' % (
                                                plus_per_die_of_thrust,
                                                plus_per_die_of_thrust_string))

        # Show the 'why'
        if damage_modified:
            kick_damage_why.append('  ...for a kick damage total = %dd%+d' % (
                                            kick_damage['num_dice'],
                                            kick_damage['plus']))
            if damage_array is not None:
                damage_str = self.damage_to_string(damage_array)
                punch_damage_why.append('  ...for a punch damage total = %s' %
                                        damage_str)
            else:
                punch_damage_why.append(
                                '  ...for a punch damage total = %dd%+d' % (
                                                punch_damage['num_dice'],
                                                punch_damage['plus']))


        # Assemble final damage and 'why'

        # NOTE: doesn't handle fangs and such which have a damage type of
        # impaling, etc.
        damage_type_str = self.__get_damage_type_str('cr')

        if damage_array is None:
            damage_array = [{
                'attack_type': None,
                'num_dice': punch_damage['num_dice'],
                'plus': punch_damage['plus'],
                'damage_type': damage_type_str
            }]
        result['punch_damage'] = self.damage_to_string(damage_array)

        if kick_damage is not None:
            damage_array = [{
                'attack_type': None,
                'num_dice': kick_damage['num_dice'],
                'plus': kick_damage['plus'],
                'damage_type': damage_type_str
            }]
            result['kick_damage'] = self.damage_to_string(damage_array)

        # Using this order because that's the order the data is shown in the
        # regular window.
        result['why'].extend(parry_why)
        result['why'].extend(punch_why)
        result['why'].extend(punch_damage_why)
        result['why'].extend(kick_why)
        result['why'].extend(kick_damage_why)

        return result

    def get_weapons_unarmed_skills(self,
                                   weapon  # None or dict from Game File
                                   ):
        '''
        Determines whether this weapon (which may be None) uses the unarmed
        combat skills.  That's basically a blackjack or brass knuckles but
        there may be more.  Assumes weapon's skill is the most advanced skill
        supported.

        Returns array of skills supported by this weapon.
        '''

        # Skills in increasing order of difficulty
        all_unarmed_skills = ['dx', 'Brawling', 'Boxing', 'Karate']

        if weapon is None:  # No weapon uses unarmed skills by definition
            return all_unarmed_skills

        if weapon['skill'] not in all_unarmed_skills:
            return None

        for i, skill in enumerate(all_unarmed_skills):
            if weapon['skill'] == skill:
                # Returns all of the skills through the matched one
                return all_unarmed_skills[:i+1]

        return ['dx']  # Camel in Cairo -- should never get here

    def heal_fighter(self,
                     fighter,   # Fighter object
                     world      # World object
                     # TODO: prefs - for parent
                     ):
        '''
        Removes all injury (and their side-effects) from a fighter.
        '''
        super(GurpsRuleset, self).heal_fighter(fighter, world)
        fighter.details['shock'] = 0
        fighter.details['stunned'] = False
        fighter.details['check_for_death'] = False

    def initiative(self,
                   fighter  # Fighter object
                   ):
        '''
        Generates a tuple of numbers for a creature that determines the order
        in which the creatures get to act in a fight.  Sorting creatures by
        their tuples (1st sorting key on the 1st element of the tuple, ...)
        will put them in the proper order.

        Returns: the 'initiative' tuple
        '''
        return (fighter.details['current']['basic-speed'],
                fighter.details['current']['dx'],
                ca_ruleset.Ruleset.roll(1, 6)
                )

    def is_creature_consistent(self,
                               name,     # string: creature's name
                               creature  # dict from Game File
                               ):
        '''
        Make sure creature has skills for all their stuff.  Trying to make
        sure that one or the other of the skills wasn't entered incorrectly.
        '''
        result = True

        if 'skills' not in creature:
            return result

        unarmed_skills = self.get_weapons_unarmed_skills(None)

        for item in creature['stuff']:
            # NOTE: if the skill is one of the unarmed skills, then the skill
            # defaults to DX and that's OK -- we don't have to tell the user
            # about this.
            if ('skill' in item and
                                item['skill'] not in creature['skills'] and
                                item['skill'] not in unarmed_skills):
                self._window_manager.error([
                    'Creature "%s"' % name,
                    '  has item "%s"' % item['name'],
                    '  that requires skill "%s"' % item['skill'],
                    '  but not the skill to use it'])
                result = False
        return result

    def make_empty_creature(self):
        '''
        Builds the minimum legal character detail (the dict that goes into the
        Game File).  You can feed this to the constructor of a Fighter.  First,
        however, you need to install it in the World's Game File so that it's
        backed-up and recognized by the rest of the software.

        Returns: the dict.
        '''
        to_monster = super(GurpsRuleset, self).make_empty_creature()
        to_monster.update({'aim': { 'braced': False, 'rounds': 0 },
                           'skills': { },
                           'shock': 0,
                           'stunned': False,
                           'advantages': { },
                           'actions_this_turn': [],
                           'check_for_death': False,
                           'posture': 'standing'})
        to_monster['permanent'] = copy.deepcopy({'fp': 10,
                                                 'iq': 10,
                                                 'hp': 10,
                                                 'wi': 10,
                                                 'st': 10,
                                                 'ht': 10,
                                                 'dx': 10,
                                                 'basic-move': 5,
                                                 'basic-speed': 5,
                                                 'per': 10})
        to_monster['current'] = copy.deepcopy(to_monster['permanent'])
        return to_monster

    def reset_aim(self,                         # Public to support testing
                  fighter           # Fighter object
                  ):
        '''
        Resets the aim for the Fighter.

        Returns: nothing.
        '''
        fighter.details['aim']['rounds'] = 0
        fighter.details['aim']['braced'] = False

    def search_one_creature(self,
                            name,        # string containing the name
                            group,       # string containing the group
                            creature,    # dict describing the creature
                            look_for_re  # compiled Python regex
                            ):
        '''
        Looks through a creature for the regular expression |look_for_re|.

        Returns: dict: with name, group, location (where in the character the
        regex was found), and notes (text for display to the user).
        '''

        result = super(GurpsRuleset, self).search_one_creature(name,
                                                               group,
                                                               creature,
                                                               look_for_re)

        if 'advantages' in creature:
            for advantage in creature['advantages']:
                if look_for_re.search(advantage):
                    result.append(
                        {'name': name,
                         'group': group,
                         'location': 'advantages',
                         'notes': '%s=%d' % (
                                        advantage,
                                        creature['advantages'][advantage])})

        if 'skills' in creature:
            for skill in creature['skills']:
                if look_for_re.search(skill):
                    result.append(
                            {'name': name,
                             'group': group,
                             'location': 'skills',
                             'notes': '%s=%d' % (skill,
                                                 creature['skills'][skill])})

        return result

    def start_fight(self,
                    fighter  # Fighter object
                    ):
        '''
        Removes all the ruleset-related stuff from the old fight except injury.
        '''
        fighter.details['shock'] = 0
        fighter.details['stunned'] = False
        fighter.details['check_for_death'] = False
        fighter.details['posture'] = 'standing'
        self.reset_aim(fighter)

    def start_turn(self,
                   fighter,         # Fighter object
                   fight_handler    # FightHandler object
                   ):
        '''
        Performs all of the stuff required for a Fighter to start his/her
        turn.  Does all the consciousness/death checks, etc.

        Returns: nothing
        '''
        playing_back = (False if fight_handler is None else
                                        fight_handler.world.playing_back)
        # B426 - FP check for consciousness
        if fighter.is_conscious() and not playing_back:
            if fighter.details['current']['fp'] <= 0:
                pass_out_menu = [(('roll <= WILL (%s), or did nothing' %
                                    fighter.details['current']['wi']), True),
                                 ('did NOT make WILL roll', False)]
                made_will_roll = self._window_manager.menu(
                    'On Action: roll <= WILL or pass out due to FP (B426)',
                    pass_out_menu)
                if not made_will_roll:
                    self.do_action(fighter,
                                   {'action-name': 'set-consciousness',
                                    'level': ca_fighter.Fighter.UNCONSCIOUS},
                                   fight_handler)

        # B327 -- immediate check for death
        if (fighter.is_conscious() and fighter.details['check_for_death'] and
                                                            not playing_back):
            dead_menu = [
                (('roll <= HT (%d)' % fighter.details['current']['ht']), True),
                ('did NOT make HT roll', False)]
            made_ht_roll = self._window_manager.menu(
                ('%s: roll <= HT or DIE (B327)' % fighter.name),
                 dead_menu)

            if not made_ht_roll:
                self.do_action(fighter,
                               {'action-name': 'set-consciousness',
                                'level': ca_fighter.Fighter.DEAD},
                               fight_handler)

        fighter.details['check_for_death'] = False  # Only show/roll once

        # B327 -- checking on each round whether the fighter is still
        # conscious

        if (fighter.is_conscious() and
                                    fighter.details['current']['hp'] <= 0 and
                                    not playing_back):
            unconscious_roll = fighter.details['current']['ht']
            if 'High Pain Threshold' in fighter.details['advantages']:
                unconscious_roll += 3

                menu_title = (
                    '%s: HP < 0: roll <= HT+3 (%d) or pass out (B327,B59)' %
                    (fighter.name, unconscious_roll))
            else:
                menu_title = (
                    '%s: HP < 0: roll <= HT (%d) or pass out (B327)' %
                    (fighter.name, unconscious_roll))

            pass_out_menu = [
                    ('Succeeded (roll <= %d) - NOT unconscious' %
                        unconscious_roll, True),
                    ('Failed (roll > %d) - unconscious' %
                        unconscious_roll, False)]
            made_ht_roll = self._window_manager.menu(menu_title, pass_out_menu)

            if not made_ht_roll:
                self.do_action(fighter,
                               {'action-name': 'set-consciousness',
                                'level': ca_fighter.Fighter.UNCONSCIOUS},
                               fight_handler)

        fighter.details['actions_this_turn'] = []

    #
    # Protected and Private Methods
    #

    def _adjust_hp(self,
                   fighter,         # Fighter object
                   action,          # {'action-name': 'adjust-hp',
                                    #  'adj': <number (usually < 0) HP change>,
                                    #  'comment': <string>, # optional
                                    #  'quiet': <bool - use defaults for all
                                    #            user interactions.> }
                   fight_handler    # FightHandler object
                   ):
        '''
        NOTE: This is a huge tangle because, for the GurpsRuleset, we need to
        ask questions (i.e., whether or not to subtract DR from the HP).
        Because of that, there are 2 events: 1) adjust-hp asks the question
        and generates the 2nd event adjust-hp-really EXCEPT for playback mode,
        where it does nothing.  2) adjust-hp-really contains the post-DR
        adjustment and actually reduces the HP.

        ON TOP OF THAT, adjust-hp is handled differently than the rest of the
        actions.  Normally, there's a Ruleset.__xxx and a GurpsRuleset.__xxx
        and they're called in a cascaded manner:

                            GurpsRuleset       Ruleset
                                 |                |
                                 -                -
                    do_action ->| |- do_action ->| |- __xxx -+
                                | |              | |         |
                                | |              | ||<-------+
                                | |<- - - - - - -| |
                                | |- __xxx -+     -
                                | |         |     |
                                | ||<-------+     |
                                 -                |
                                 |                |

        _adjust_hp, though, is PROTECTED (not private) so Ruleset::do_action
        actually calls GurpsRuleset::_xxx and Ruleset::_xxx is overridden:

                            GurpsRuleset         Ruleset
                                 |                  |
                                 -                  -
                    do_action ->| |-- do_action -->| |- _adjust_hp --+
                                | |                | |               |
                                | ||<- _adjust_hp -------------------+
                                | ||- - - - - - - >| |
                                | |                | |
                                | |<- - - - - - - -| |
                                 -                  -
                                 |                  |

        Ruleset::_adjust_hp never gets called for the adjust-hp action.
        Ruleset's function gets called, directly, by the 2nd (GurpsRulest-
        specific) action.

        We do things this way because a) GurpsRuleset::_adjust_hp modifies the
        adj (in the case of armor) so we can't call the Ruleset's version
        first (it has bad data) and b) we can't ask questions in an action
        during playback.
        '''

        if fight_handler.world.playing_back:
            # This is called from Ruleset::do_action so we have to have a
            # return value that works, there.
            return ca_ruleset.Ruleset.HANDLED_OK

        adj = action['adj']
        quiet = False if 'quiet' not in action else action['quiet']

        if adj < 0:
            # Hit location (just for flavor, not for special injury)
            table_lookup = (random.randint(1,6) +
                            random.randint(1,6) +
                            random.randint(1,6))
            hit_location = GurpsRuleset.hit_location_table[table_lookup]

            window_text = [
                [{'text': ('...%s\'s %s' % (fighter.name, hit_location)),
                  'mode': curses.A_NORMAL}]
                           ]

            # Adjust for armor
            dr = 0
            dr_text_array = []
            use_armor = False
            armor, armor_index = fighter.get_current_armor()
            if armor is not None:
                dr += armor['dr']
                dr_text_array.append(armor['name'])

            if 'Damage Resistance' in fighter.details['advantages']:
                # GURPS rules, B46, 5 points per level of DR advantage
                dr += (fighter.details['advantages']['Damage Resistance']/5)
                dr_text_array.append('DR Advantage')

            if not quiet and dr != 0:
                use_armor_menu = [('yes', True), ('no', False)]
                use_armor = self._window_manager.menu('Use Armor\'s DR?',
                                                                use_armor_menu)
            if use_armor:
                if dr >= -adj:
                    window_text = [
                        [{'text': 'The armor absorbed all the damage',
                          'mode': curses.A_NORMAL}]
                    ]
                    self._window_manager.display_window(
                                    ('Did *NO* damage to %s' % fighter.name),
                                    window_text)
                    return ca_ruleset.Ruleset.HANDLED_OK

                original_adj = adj

                adj += dr
                action['adj'] = adj

                dr_text = '; '.join(dr_text_array)
                window_text.append([{'text':'', 'mode': curses.A_NORMAL}])
                window_text.append(
                    [{'text': ('%s was wearing %s (total dr:%d)' % (
                                                              fighter.name,
                                                              dr_text,
                                                              dr)),
                      'mode': curses.A_NORMAL}]
                                  )
                window_text.append(
                    [{'text': ('so adj(%d) - dr(%d) = damage (%d)' % (
                                                              -original_adj,
                                                              dr,
                                                              -adj)),
                      'mode': curses.A_NORMAL}]
                                  )

                self._window_manager.display_window(
                                    ('Did %d hp damage to...' % -adj),
                                    window_text)

            # Check for Death (B327)
            adjusted_hp = fighter.details['current']['hp'] + adj

            if adjusted_hp <= -(5 * fighter.details['permanent']['hp']):
                self.do_action(fighter,
                               {'action-name': 'set-consciousness',
                                'level': ca_fighter.Fighter.DEAD},
                               fight_handler)
            else:
                threshold = -fighter.details['permanent']['hp']
                while fighter.details['current']['hp'] <= threshold:
                    threshold -= fighter.details['permanent']['hp']
                if adjusted_hp <= threshold:
                    self.do_action(fighter,
                                   {'action-name': 'check-for-death',
                                    'value': True},
                                   fight_handler)

            # Check for Major Injury (B420)
            if -adj > (fighter.details['permanent']['hp'] / 2):
                (SUCCESS, SIMPLE_FAIL, BAD_FAIL) = range(3)
                total = fighter.details['current']['ht']
                if 'High Pain Threshold' in fighter.details['advantages']:
                    total = fighter.details['current']['ht'] + 3
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT+3 (%d) or be stunned' %
                                                                        total)
                #elif 'Low Pain Threshold' in fighter.details['advantages']:
                #    total = fighter.details['current']['ht'] - 4
                #    menu_title = (
                #       'Major Wound (B420): Roll vs. HT-4 (%d) or be stunned' %
                #                                                        total)
                else:
                    total = fighter.details['current']['ht']
                    menu_title = (
                        'Major Wound (B420): Roll vs. HT (%d) or be stunned' %
                                                                        total)

                stunned_menu = [
                   ('Succeeded (roll <= HT (%d))' % total,
                                 GurpsRuleset.MAJOR_WOUND_SUCCESS),
                   ('Missed roll by < 5 (roll < %d) -- stunned' % (total+5),
                                 GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL),
                   ('Missed roll by >= 5 (roll >= %d -- unconscious)' %
                                                                    (total+5),
                                 GurpsRuleset.MAJOR_WOUND_BAD_FAIL),
                               ]
                stunned_results = self._window_manager.menu(menu_title,
                                                            stunned_menu)
                if stunned_results == GurpsRuleset.MAJOR_WOUND_BAD_FAIL:
                    self.do_action(fighter,
                                   {'action-name': 'set-consciousness',
                                    'level': ca_fighter.Fighter.UNCONSCIOUS},
                                   fight_handler)
                elif stunned_results == GurpsRuleset.MAJOR_WOUND_SIMPLE_FAIL:
                    self.do_action(fighter,
                                   {'action-name': 'change-posture',
                                    'posture': 'lying'},
                                   fight_handler)
                    self.do_action(fighter,
                                   {'action-name': 'stun',
                                    'stun': True},
                                   fight_handler)

        if 'High Pain Threshold' not in fighter.details['advantages']:  # B59
            # Shock (B419) is cumulative but only to a maximum of -4
            # Note: 'adj' is negative
            shock_level = fighter.details['shock'] + adj
            if shock_level < -4:
                shock_level = -4
            self.do_action(fighter,
                           {'action-name': 'shock', 'value': shock_level},
                           fight_handler)

        # WILL roll or lose aim
        if fighter.details['aim']['rounds'] > 0:
            aim_menu = [('made WILL roll', True),
                        ('did NOT make WILL roll', False)]
            made_will_roll = self._window_manager.menu(
                ('roll <= WILL (%d) or lose aim' %
                                            fighter.details['current']['wi']),
                aim_menu)
            if not made_will_roll:
                self.do_action(fighter, {'action-name': 'reset-aim'}, fight_handler)

        # Have to copy the action because using the old one confuses the
        # do_action routine that called this function.
        new_action = copy.deepcopy(action)
        new_action['action-name'] = 'adjust-hp-really'
        self.do_action(fighter, new_action, fight_handler)
        return ca_ruleset.Ruleset.HANDLED_OK

    def __adjust_hp_really(self,
                           fighter,         # Fighter object
                           action,          # {'action-name': 'adjust-hp-really',
                                            #  'comment': <string>, # optional
                                            #  'adj': <number = HP change>,
                                            #  'quiet': <bool - use defaults
                                            #            for all user
                                            #            interactions.> }
                           fight_handler    # FightHandler object
                           ):
        '''
        Action handler for GurpsRuleset.

        This is the 2nd part of a 2-part action.  This action
        ('adjust-hp-really') actually perfoms all the actions and
        side-effects of changing the hit-points.  See
        |GurpsRuleset::_adjust_hp| for an idea of how this method is used.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        super(GurpsRuleset, self)._adjust_hp(fighter, action, fight_handler)
        return None  # No timers

    def __cast_spell(self,
                     fighter,       # Fighter object
                     action,        # {'action-name': 'cast-spell'
                                    #  'spell-index': <index in 'spells'>,
                                    #  'complete spell': <dict> # this
                                    #     is a combination of the spell
                                    #     in the character details and
                                    #     the same spell from the
                                    #     ruleset
                                    #  'comment': <string>, # optional
                                    #  'part': 2 # optional
                     fight_handler  # FightHandler object
                     ):
        '''
        Action handler for GurpsRuleset.

        Handles the action of casting a magic spell.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  The 2nd part of this
            # action actually perfoms all the actions and side-effects of
            # casting a spell.  This is mostly a bunch of timers.

            complete_spell = action['complete spell']

            # Charge the spell caster for the spell.

            if complete_spell['cost'] > 0:
                self.do_action(fighter,
                               {'action-name': 'adjust-fp',
                                'adj': -complete_spell['cost']},
                               fight_handler,
                               logit=False)

            # Duration Timer

            # If the spell lasts any time at all, put a timer up so that we see
            # that it's active

            duration_timer = ca_timers.Timer(None)
            if complete_spell['duration'] > 0:
                duration_timer.from_pieces(
                           {'parent-name': fighter.name,
                            'rounds': complete_spell['duration'] -
                                            ca_timers.Timer.announcement_margin,
                            'string': 'CAST SPELL (%s) ACTIVE' %
                                                        complete_spell['name']
                           })

            # Casting Timer

            casting_timer = ca_timers.Timer(None)
            text = [('Casting (%s) @ skill (%d): %s' % (
                                                    complete_spell['name'],
                                                    complete_spell['skill'],
                                                    complete_spell['notes'])),
                    ' Defense: none',
                    ' Move: none']

            actions = {'timer': duration_timer.details}
            if complete_spell['duration'] == 0:
                actions['announcement'] = ('CAST SPELL (%s) FIRED' %
                                                        complete_spell['name'])

            casting_timer.from_pieces({'parent-name': fighter.name,
                               'rounds': complete_spell['casting time'] -
                                            ca_timers.Timer.announcement_margin,
                               'string': text,
                               'actions': actions})
            casting_timer.mark_owner_as_busy()  # When casting, the owner is busy

            # Opponent's Timers

            if 'opponent' in action and fight_handler is not None:
                opponent = fight_handler.get_fighter_object(
                                                action['opponent']['name'],
                                                action['opponent']['group'])

                spell_timer = ca_timers.Timer(None)
                if complete_spell['duration'] > 0:
                    spell_timer.from_pieces(
                             {'parent-name': opponent.name,
                              'rounds': complete_spell['duration'] -
                                            ca_timers.Timer.announcement_margin,
                              'string': 'SPELL "%s" AGAINST ME' %
                                                        complete_spell['name']
                             })

                delay_timer = ca_timers.Timer(None)

                actions = {'timer': spell_timer.details}
                if complete_spell['duration'] == 0:
                    actions['announcement'] = ('SPELL (%s) AGAINST ME FIRED' %
                                                        complete_spell['name'])

                # Add 1 to the timer because the first thing the opponent will
                # see is a decrement (the caster only sees the decrement on the
                # _next_ round)
                delay_timer.from_pieces(
                         {'parent-name': opponent.name,
                          'rounds': 1 + complete_spell['casting time'] -
                                            ca_timers.Timer.announcement_margin,
                          'string': ('Waiting for "%s" spell to take affect' %
                                                    complete_spell['name']),
                          'actions': actions
                         })

                opponent.timers.add(delay_timer)

            return casting_timer
        else:
            # This is the 1st part of a 2-part action.  This 1st part of this
            # action asks questions of the user and sends the second part.
            # The 1st part isn't executed when playing back.

            if fight_handler is not None and fight_handler.world.playing_back:
                return None  # No timers

            # Assemble the spell from the ruleset's copy of it and the Fighter's
            # copy of it.

            spell_index = action['spell-index']
            spell = fighter.details['spells'][spell_index]

            if spell['name'] not in GurpsRuleset.spells:
                self._window_manager.error(
                    ['Spell "%s" not in GurpsRuleset.spells' % spell['name']]
                )
                return None  # No timers
            complete_spell = copy.deepcopy(spell)
            complete_spell.update(GurpsRuleset.spells[spell['name']])

            # Duration

            if complete_spell['duration'] is None:
                title = 'Duration for (%s) - see (%s) ' % (
                                                        complete_spell['name'],
                                                        complete_spell['notes'])
                height = 1
                width = len(title)
                duration_string = ''
                while len(duration_string) <= 0:
                    duration_string = self._window_manager.input_box(height,
                                                                     width,
                                                                     title)
                complete_spell['duration'] = int(duration_string)

            # Cost

            if complete_spell['cost'] is None:
                title = 'Cost to cast (%s) - see (%s) ' % (
                                                        complete_spell['name'],
                                                        complete_spell['notes'])
                height = 1
                width = len(title)
                cost_string = ''
                while len(cost_string) <= 0:
                    cost_string = self._window_manager.input_box(height,
                                                                 width,
                                                                 title)
                complete_spell['cost'] = int(cost_string)

            # M8 - High skill level costs less
            skill = complete_spell['skill'] - 15
            while skill >= 0:
                complete_spell['cost'] -= 1
                skill -= 5
            if complete_spell['cost'] <= 0:
                complete_spell['cost'] = 0

            # Casting time

            if (complete_spell['casting time'] is None or
                                        complete_spell['casting time'] == 0):
                title = 'Seconds to cast (%s) - see (%s) ' % (
                                                    complete_spell['name'],
                                                    complete_spell['notes'])
                height = 1
                width = len(title)
                casting_time_string = ''
                while len(casting_time_string) <= 0:
                    casting_time_string = self._window_manager.input_box(height,
                                                                         width,
                                                                         title)
                complete_spell['casting time'] = int(casting_time_string)

            # Opponent?

            opponent = None
            if fight_handler is not None:
                opponent = fight_handler.get_opponent_for(fighter)

            if opponent is not None:
                opponent_timer_menu = [('yes', True), ('no', False)]
                timer_for_opponent = self._window_manager.menu(
                                        ('Mark %s with spell' % opponent.name),
                                        opponent_timer_menu)
                if not timer_for_opponent:
                    opponent = None

            # Send the action for the second part

            new_action = {'action-name': 'cast-spell',
                          'complete spell': complete_spell,
                          'part': 2}

            if opponent is not None:
                new_action['opponent'] = {'name': opponent.name,
                                          'group': opponent.group}

            self.do_action(fighter, new_action, fight_handler)

            return None  # No new timers

    def __change_posture(self,
                         fighter,          # Fighter object
                         action,           # {'action-name': 'change-posture',
                                           #  'posture': <string> # posture
                                           #        from GurpsRuleset.posture
                                           #  'comment': <string>, # optional
                         fight_handler     # FightHandler object
                         ):
        '''
        Action handler for GurpsRuleset.

        Changes the posture of the Fighter.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['posture'] = action['posture']
        self.reset_aim(fighter)

        # Timer

        timer = ca_timers.Timer(None)

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1 - ca_timers.Timer.announcement_margin,
                           'string': ['Change posture',
                                      ' NOTE: crouch 1st action = free',
                                      '       crouch->stand = free',
                                      '       kneel->stand = step',
                                      ' Defense: any',
                                      ' Move: none'] })

        return timer

    def __check_for_death(self,
                          fighter,          # Fighter object
                          action,           # {'action-name': 'check-for-death',
                                            #  'value': <bool>,
                                            #  'comment': <string>, # optional
                          fight_handler     # FightHandler object
                          ):
        '''
        Action handler for GurpsRuleset.

        Sets the Fighter's 'check_for_death' field.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['check_for_death'] = action['value']
        return None  # No timer

    def __damage_FP(self,
                    param    # {'view': xxx, 'view-opponent': xxx,
                             #  'current': xxx, 'current-opponent': xxx,
                             #  'fight_handler': <fight handler> } where
                             # xxx are Fighter objects
                    ):
        '''
        Command ribbon method.

        Figures out from whom to remove fatigue points and removes them (via
        an action).

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if param is None:
            return True
        elif param['view'] is not None:
            fp_recipient = param['view']
        elif param['current-opponent'] is not None:
            fp_recipient = param['current-opponent']
        elif param['current'] is not None:
            fp_recipient = param['current']
        else:
            return True

        title = 'Reduce (%s\'s) FP By...' % fp_recipient.name
        height = 1
        width = len(title)
        adj_string = self._window_manager.input_box(height, width, title)
        if len(adj_string) <= 0:
            return True
        adj = -int(adj_string)  # NOTE: SUBTRACTING the adjustment

        if adj < 0:
            comment = '(%s) lost %d FP' % (fp_recipient.name, -adj)
        else:
            comment = '(%s) regained %d FP' % (fp_recipient.name, adj)

        fight_handler = (None if 'fight_handler' not in param
                                                else param['fight_handler'])
        self.do_action(fp_recipient,
                       {'action-name': 'adjust-fp', 'adj': adj, 'comment': comment},
                       fight_handler)

        return True  # Keep going

    def __do_adjust_fp(self,
                       fighter,       # Fighter object
                       action,        # {'action-name': 'adjust-fp',
                                      #  'adj': <int> # number to add to FP
                                      #  'comment': <string>, # optional
                       fight_handler  # FightHandler object (for logging)
                       ):
        '''
        Action handler for GurpsRuleset.

        Adjusts the fatigue points of a Fighter and manages all of the side-
        effects associated therewith.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        # See B426 for consequences of loss of FP
        adj = action['adj']  # Adj is likely negative

        # If FP go below zero, you lose HP along with FP
        hp_adj = 0
        if adj < 0  and -adj > fighter.details['current']['fp']:
            hp_adj = adj
            if fighter.details['current']['fp'] > 0:
                hp_adj += fighter.details['current']['fp']

        if hp_adj < 0:
            self.do_action(fighter,
                           {'action-name': 'adjust-hp', 'adj': hp_adj, 'quiet': True},
                           fight_handler,
                           logit=False)

        fighter.details['current']['fp'] += adj

        if (fighter.details['current']['fp'] <=
                                        -fighter.details['permanent']['fp']):
            self.do_action(fighter,
                           {'action-name': 'set-consciousness',
                            'level': ca_fighter.Fighter.UNCONSCIOUS},
                           fight_handler,
                           logit=False)
        return None  # No timer

    def __do_adjust_shock(self,
                 fighter,       # Fighter object
                 action,        # {'action-name': 'shock',
                                #  'value': <int> # level to which to set shock
                                #  'comment': <string>, # optional
                 fight_handler  # FightHandler object
                 ):
        '''
        Action handler for GurpsRuleset.

        Changes the Fighter's shock value.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['shock'] = action['value']
        return None  # No timer

    def __do_aim(self,
                 fighter,       # Fighter object
                 action,        # {'action-name': 'aim',
                                #  'braced': <bool> # see B364
                                #  'comment': <string>, # optional
                 fight_handler  # FightHandler object
                 ):
        '''
        Action handler for GurpsRuleset.

        Peforms the 'aim' action.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        if fight_handler is not None and not fight_handler.world.playing_back:
            if fighter.details['opponent'] is None:
                fight_handler.pick_opponent()

        rounds = fighter.details['aim']['rounds']
        if rounds == 0:
            fighter.details['aim']['braced'] = action['braced']
            fighter.details['aim']['rounds'] = 1
        elif rounds < 3:
            fighter.details['aim']['rounds'] += 1

        # Timer

        timer = ca_timers.Timer(None)
        timer.from_pieces(
            {'parent-name': fighter.name,
             'rounds': 1 - ca_timers.Timer.announcement_margin,
             'string': [('Aim%s' % (' (braced)' if action['braced'] else '')),
                         ' Defense: any loses aim',
                         ' Move: step']
            })

        return timer

    def __do_attack(self,
                   fighter,          # Fighter object
                   action,           # {'action-name': 'attack' | 'all-out-attack' |
                                     #          'move-and-attack'
                                     #  'comment': <string>, # optional
                   fight_handler     # FightHandler object
                   ):
        '''
        Action handler for GurpsRuleset.

        Does the ruleset-specific stuff for an attack.  MOSTLY, that's just
        creating the timer, though, since I don't currently have the code roll
        anything (putting this in a comment will come back to bite me when I
        inevitably add that capability to the code but not read and repair the
        comments).

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = ca_timers.Timer(None)

        move = fighter.details['current']['basic-move']
        if action['action-name'] == 'all-out-attack':
            text = ['All out attack',
                    ' Defense: none',
                    ' Move: 1/2 = %d' % (move/2)]

        elif action['action-name'] == 'attack':
            text = ['Attack', ' Defense: any', ' Move: step']

        elif action['action-name'] == 'move-and-attack':
            # FP: B426
            if (fighter.details['current']['fp'] <
                            (fighter.details['permanent']['fp'] / 3)):
                move_string = 'half=%d (FP:B426)' % (move/2)
            else:
                move_string = 'full=%d' % move

            # Move and attack info
            text = ['Move & Attack',
                    ' Defense: Dodge,block',
                    ' Move: %s' % move_string]

            weapon, throw_away = fighter.get_current_weapon()
            holding_ranged = (False if weapon is None else
                                        (weapon['type'] == 'ranged weapon'))
            if fight_handler is None:
                opponent = None
            else:
                opponent = fight_handler.get_opponent_for(fighter)
            if weapon is None:
                unarmed_skills = self.get_weapons_unarmed_skills(weapon)
                unarmed_info = self.get_unarmed_info(fighter,
                                                     opponent,
                                                     weapon,
                                                     unarmed_skills)
                to_hit = unarmed_info['punch_skill'] - 4
                to_hit = 9 if to_hit > 9 else to_hit
                text.append(' Punch to-hit: %d' % to_hit)

                to_hit = unarmed_info['kick_skill'] - 4
                to_hit = 9 if to_hit > 9 else to_hit
                text.append(' Kick to-hit: %d' % to_hit)
            else:
                to_hit, ignore_why = self.get_to_hit(fighter, opponent, weapon)
                if holding_ranged:
                    to_hit -= 2  # or weapon's bulk rating, whichever is worse
                else:
                    to_hit -= 4

                to_hit = 9 if to_hit > 9 else to_hit
                text.append(' %s to-hit: %d' % (weapon['name'], to_hit))

        else:
            text = ['<<UNHANDLED ACTION: %s' % action['action-name']]

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1 - ca_timers.Timer.announcement_margin,
                           'string': text})
        return timer

    def __do_nothing(self,
                     fighter,      # Fighter object
                     action,       # {'action-name': 'concentrate' | 'evaluate' |
                                   #          'feint' | 'move' | 'nothing' |
                                   #          'pick-opponent' | 'use-item' |
                                   #          'user-defined',
                                   #  'comment': <string>, # optional
                                   #
                                   # NOTE: Some actions have other
                                   # parameters used buy |Ruleset|
                                   #
                     fight_handler  # FightHandler object
                     ):
        '''
        Action handler for GurpsRuleset.

        Does nothing but create the appropriate timer for the action.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        # Timer

        timer = ca_timers.Timer(None)

        if 'action-name' not in action:
            return None

        if action['action-name'] == 'nothing':
            text = ['Do nothing', ' Defense: any', ' Move: none']

        elif action['action-name'] == 'move':
            move = fighter.details['current']['basic-move']

            if (fighter.details['current']['fp'] <
                            (fighter.details['permanent']['fp'] / 3)):
                move_string = 'half=%d (FP:B426)' % (move/2)
            else:
                move_string = 'full=%d' % move
            text = ['Move', ' Defense: any', ' Move: %s' % move_string]

        elif action['action-name'] == 'feint':
            text = ['Feint',
                    ' Contest of melee weapon or DX',
                    '   subtract score from opp',
                    '   active defense next turn',
                    '   (for both, if all-out-attack)',
                    ' Defense: any, parry *',
                    ' Move: step']

        elif action['action-name'] == 'evaluate':
            text = ['Evaluate', ' Defense: any', ' Move: step']


        elif action['action-name'] == 'concentrate':
            text = ['Concentrate', ' Defense: any w/will roll', ' Move: step']

        elif action['action-name'] == 'use-item':
            item = fighter.equipment.get_item_by_index(action['item-index'])
            text = [('Use %s' % item['name']),
                    ' Defense: (depends)',
                    ' Move: (depends)']

        elif action['action-name'] == 'user-defined':
            text = ['User-defined action']

        elif action['action-name'] == 'pick-opponent':
            return None

        else:
            text = ['<<UNHANDLED ACTION: %s' % action['action-name']]

        timer.from_pieces( {'parent-name': fighter.name,
                            'rounds': 1 - ca_timers.Timer.announcement_margin,
                            'string': text} )

        return timer

    def __do_reload(self,
                    fighter,  # Fighter object
                    action,   # {'action-name': 'reload',
                              #  'notimer': <bool>, # whether to
                              #                       return a timer
                              #                       for the fighter
                              #                       -- optional
                              #  'comment': <string>, # optional
                              #  'quiet': <bool>    # use defaults for
                              #                       all user
                              #                       interactions
                              #                       -- optional
                              #  'time': <duration>
                              #  'part': 2          # optional }
                              # }
                    fight_handler,    # FightHandler object
                    ):
        '''
        Action handler for GurpsRuleset.

        Handles reloading a weapon.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''

        if 'part' in action and action['part'] == 2:
            # This is the 2nd part of a 2-part action.  This part of the action
            # actually perfoms all the GurpsRuleset-specific actions and
            # side-effects of reloading the Fighter's current weapon.  Note
            # that a lot of the obvious part is done by the base class Ruleset.

            self.reset_aim(fighter)

            # Timer

            timer = None
            if 'notimer' not in action or not action['notimer']:
                timer = ca_timers.Timer(None)
                timer.from_pieces(
                    {'parent-name': fighter.name,
                     'rounds': action['time'] - ca_timers.Timer.announcement_margin,
                     'string': 'RELOADING'} )

                timer.mark_owner_as_busy()  # When reloading, the owner is busy

            return timer
        else:
            # This is the 1st part of a 2-part action.  This part of the
            # action asks questions of the user and sends the second part
            # The 1st part isn't executed when playing back.

            if fight_handler is not None and fight_handler.world.playing_back:
                return None  # No timer

            weapon, weapon_index = fighter.get_current_weapon()
            if weapon is None or 'ammo' not in weapon:
                return None  # No timer

            # Check to see if we need a reload at all

            if weapon['ammo']['shots_left'] == weapon['ammo']['shots']:
                return None  # No timer

            # If we do, how long will it take?

            reload_time = weapon['reload']

            # B43: combat reflexes
            if 'Combat Reflexes' in fighter.details['advantages']:
                reload_time -= 1

            quiet = False if 'quiet' not in action else action['quiet']
            if not quiet:
                # B194: fast draw
                if 'Fast-Draw (Ammo)' in fighter.details['skills']:
                    skill_menu = [('made SKILL roll', True),
                                  ('did NOT make SKILL roll', False)]
                    made_skill_roll = self._window_manager.menu(
                        ('roll <= fast-draw skill (%d)' %
                                fighter.details['skills']['Fast-Draw (Ammo)']),
                        skill_menu)

                    if made_skill_roll:
                        reload_time -= 1

            if reload_time > 0:
                new_action = {'action-name': 'reload',
                              'time': reload_time,
                              'part': 2}
                if 'notimer' in action:
                    new_action['notimer'] = action['notimer']
                self.do_action(fighter, new_action, fight_handler)

            return None  # No timer

    def __draw_weapon(self,
                      fighter,          # Fighter object
                      action,           # {'action-name': 'draw-weapon',
                                        #  'weapon-index': <int> # index in
                                        #       fighter.details['stuff'],
                                        #       None drops weapon
                                        #  'comment': <string>, # optional
                      fight_handler,    # FightHandler object
                      ):
        '''
        Action handler for GurpsRuleset.

        Does the ruleset-specific stuff to draw or holster a weapon.  The
        majority of the work for this is actually done in the base class.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = ca_timers.Timer(None)

        weapon, throw_away = fighter.get_current_weapon()

        #if 'Fast-Draw (Pistol)' in fighter.details['skills']:
        #    skill_menu = [('made SKILL roll', True),
        #                  ('did NOT make SKILL roll', False)]
        #    made_skill_roll = self._window_manager.menu(
        #        ('roll <= fast-draw skill (%d)' %
        #                fighter.details['skills']['Fast-Draw (Ammo)']),
        #        skill_menu)
        #
        #    if made_skill_roll:
        #        ...

        title = 'Holster weapon' if weapon is None else (
                                                'Draw %s' % weapon['name'])

        timer.from_pieces({'parent-name': fighter.name,
                           'rounds': 1 - ca_timers.Timer.announcement_margin,
                           'string': [title, ' Defense: any', ' Move: step']})
        return timer

    def __get_damage_type_str(self,
                              damage_type   # <string> key in
                                            #   GurpsRuleset.damage_mult
                              ):
        '''
        Expands the short-hand version of damage type with the long form (that
        includes the damage multiplier).

        Returns the long form string.
        '''
        if damage_type in GurpsRuleset.damage_mult:
            damage_type_str = '%s=x%.1f' % (
                                        damage_type,
                                        GurpsRuleset.damage_mult[damage_type])
        else:
            damage_type_str = '%s' % damage_type
        return damage_type_str

    def _perform_action(self,
                        fighter,          # Fighter object
                        action,           # {'action-name': <action>, parameters...}
                        fight_handler,    # FightHandler object
                        logit=True        # Log into history and
                                          #  'actions_this_turn' because the
                                          #  action is not a side-effect of
                                          #  another action
                        ):
        '''
        This routine delegates actions to routines that perform the action.
        The action routine may return a timer.  _this_ routine adds the timer
        to the Fighter.  That timer is there, primarily, to keep track of what
        the Fighter did but it can also mark the Fighter as busy for a
        multi-round action.

        Returns: nothing
        '''

        # Label the action so playback knows who receives it.

        action['fighter'] = {}
        action['fighter']['name'] = fighter.name
        action['fighter']['group'] = fighter.group

        # PP = pprint.PrettyPrinter(indent=3, width=150)
        # PP.pprint(action)

        # The 2-part actions are used when an action needs to ask questions
        # of the user.  The original action asks the questions and sends the
        # 'part 2' action with all of the answers.  When played back, the
        # original action just returns.  That way, there are no questions on
        # playback and the answers are the same as they were the first time.

        has_2_parts = {
            'cast-spell' : True,
            'reload' : True,
        }

        # Call base class' perform_action FIRST because GurpsRuleset depends on
        # the actions of the base class.  It make no sense for the base class'
        # actions to depend on the child class'.
        #
        # If there're two parts to an action (the first part asks questions
        # and the second part does the actual deed), only call the base class
        # on the second part.

        if (not action['action-name'] in has_2_parts or
                                    ('part' in action and action['part'] == 2)):
            handled = super(GurpsRuleset, self)._perform_action(fighter,
                                                                action,
                                                                fight_handler)
        else:
            handled = ca_ruleset.Ruleset.UNHANDLED

        actions = {
            'adjust-fp':            {'doit': self.__do_adjust_fp},
            'adjust-hp-really':     {'doit': self.__adjust_hp_really},
            'aim':                  {'doit': self.__do_aim},
            'all-out-attack':       {'doit': self.__do_attack},
            'attack':               {'doit': self.__do_attack},
            'cast-spell':           {'doit': self.__cast_spell},
            'change-posture':       {'doit': self.__change_posture},
            'check-for-death':      {'doit': self.__check_for_death},
            'concentrate':          {'doit': self.__do_nothing},
            'defend':               {'doit': self.__reset_aim},
            'don-armor':            {'doit': self.__reset_aim},
            'draw-weapon':          {'doit': self.__draw_weapon},
            'evaluate':             {'doit': self.__do_nothing},
            'feint':                {'doit': self.__do_nothing},
            'move':                 {'doit': self.__do_nothing},
            'move-and-attack':      {'doit': self.__do_attack},
            'nothing':              {'doit': self.__do_nothing},
            'pick-opponent':        {'doit': self.__do_nothing},
            'reload':               {'doit': self.__do_reload},
            'reset-aim':            {'doit': self.__reset_aim},
            'set-consciousness':    {'doit': self.__reset_aim},
            'shock':                {'doit': self.__do_adjust_shock},
            'stun':                 {'doit': self.__stun_action},
            'use-item':             {'doit': self.__do_nothing},
            'user-defined':         {'doit': self.__do_nothing},
        }

        if 'action-name' not in action:
            return handled

        if handled == ca_ruleset.Ruleset.HANDLED_ERROR:
            return  handled

        if action['action-name'] in actions:
            timer = None
            action_info = actions[action['action-name']]
            if action_info['doit'] is not None:
                timer = action_info['doit'](fighter, action, fight_handler)

            # If the base class has asked us not to log, we'll honor that.
            if handled != ca_ruleset.Ruleset.DONT_LOG:
                handled = ca_ruleset.Ruleset.HANDLED_OK

                if timer is not None and logit:
                    fighter.timers.add(timer)

        return handled

    def _record_action(self,
                       fighter,          # Fighter object
                       action,           # {'action-name': <action>, parameters...}
                       fight_handler,    # FightHandler object
                       handled,          # bool: whether/how the action was
                                         #   handled
                       logit=True        # Log into history and
                                         #  'actions_this_turn' because the
                                         #  action is not a side-effect of
                                         #  another action
                       ):
        '''
        Saves a performed 'action' in the Fighter's did-it-this-round list.

        Returns: nothing.
        '''
        if handled == ca_ruleset.Ruleset.DONT_LOG:
            return

        super(GurpsRuleset, self)._record_action(fighter,
                                                 action,
                                                 fight_handler,
                                                 handled,
                                                 logit)

        if handled == ca_ruleset.Ruleset.HANDLED_OK:
            if logit and 'action-name' in action:
                fighter.details['actions_this_turn'].append(action['action-name'])
        elif handled == ca_ruleset.Ruleset.UNHANDLED:
            self._window_manager.error(
                            ['action "%s" is not handled by any ruleset' %
                                                            action['action-name']])

        # Don't deal with HANDLED_ERROR

    def __reset_aim(self,
                    fighter,          # Fighter object
                    action,           # {'action-name': 'defend' | 'don-armor' |
                                      #          'reset-aim' |
                                      #          'set-consciousness',
                                      #  'comment': <string>, # optional
                    fight_handler     # FightHandler object
                    ):
        '''
        Action handler for GurpsRuleset.

        Resets any ongoing aim that the Fighter may have had.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        self.reset_aim(fighter)

        # Timer

        timer = None
        if action['action-name'] == 'defend':
            timer = ca_timers.Timer(None)
            timer.from_pieces(
                        {'parent-name': fighter.name,
                         'rounds': 1 - ca_timers.Timer.announcement_margin,
                         'string': ['All out defense',
                                    ' Defense: double',
                                    ' Move: step']} )

        elif action['action-name'] == 'don-armor':
            timer = ca_timers.Timer(None)
            armor, throw_away = fighter.get_current_armor()
            title = ('Doff armor' if armor is None else
                                                ('Don %s' % armor['name']))

            timer.from_pieces(
                        {'parent-name': fighter.name,
                         'rounds': 1 - ca_timers.Timer.announcement_margin,
                         'string': [title,
                                    ' Defense: none',
                                    ' Move: none']} )
        return timer

    def __stun(self,
               param    # {'view': xxx, 'view-opponent': xxx,
                        #  'current': xxx, 'current-opponent': xxx,
                        #  'fight_handler': <fight handler> } where
                        # xxx are Fighter objects
               ):
        '''
        Command ribbon method.

        Figures out whom to stun and stuns them.

        Returns: False to exit the current ScreenHandler, True to stay.
        '''

        if param is None:
            return True
        elif param['view'] is not None:
            stunned_dude = param['view']
        elif param['current-opponent'] is not None:
            stunned_dude = param['current-opponent']
        elif param['current'] is not None:
            stunned_dude = param['current']
        else:
            return True

        fight_handler = (None if 'fight_handler' not in param
                                                else param['fight_handler'])
        self.do_action(stunned_dude,
                       {'action-name': 'stun',
                        'stun': True,
                        'comment': ('(%s) got stunned' % stunned_dude.name)},
                       fight_handler)

        return True  # Keep going

    def __stun_action(self,
                      fighter,          # Fighter object
                      action,           # {'action-name': 'stun',
                                        #  'stun': False}
                                        #  'comment': <string>, # optional
                      fight_handler,    # FightHandler object
                      ):
        '''
        Action handler for GurpsRuleset.

        Marks the Fighter as stunned.

        Returns: Timer (if any) to add to Fighter.  Used for keeping track
            of what the Fighter is doing.
        '''
        fighter.details['stunned'] = action['stun']

        # Technically, dropping a weapon should leave the weapon in the room
        # but it's easier for game play to just holster it.  This assumes a
        # nice game where the GM just assumes the character (or one of his/
        # her party members) picks up the gun.
        self.do_action(fighter,
                       {'action-name': 'draw-weapon', 'weapon-index': None},
                       fight_handler,
                       logit=False)

        return None  # No timer
