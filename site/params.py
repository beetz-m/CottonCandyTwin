"""Parameter register of the Cotton Candy Booth twin (2 x 2 m Zuckerwatte booth, German fairground).

Every number the build uses lives here (or is DERIVED in code from entries here, with an inline status comment).
Entry: key -> (value, unit, status, source_key, note). Units: SI unless the unit column says otherwise; lengths in m.

SOURCED         stated by a public source (URL in SOURCES), checked when copied
SOURCED-VERIFY  secondary / shop listing / search snippet / LLM-relayed, or sources disagree -> check the original
STANDARD        from a regulation or standard (clause in the note)
DERIVED         computed from other entries (method in the note); reported with its weakest input
PROXY           from a comparable reference product or a generic guideline because the real value is not public
ANALOGUE        observed / scaled on a named product photo or comparable booth (named in the note)
MEASURED        measured from the built 3D assets
CALIBRATED      fitted to reproduce a sourced target (not an independent check)
ILLUSTRATIVE    plausible design choice of this reconstruction - replace when better data exist
GAP             known unknown, no value

Reference machine: Gold Medal Econo Floss 3017 export (230 V), sold in Germany as Neumaerker Econo Floss 00-51551
(identity inferred from matching specs). Photo-scaled dimensions use the manual photos (GM_MAN_EXP p5, p20, p22)
with the sourced floss band diameter (139.7 mm) as the scale bar.

Run: $E site/params.py   (prints the table; exits 1 on a missing source key)
"""

import sys
from collections import Counter

S, SV, ST, D, PX, A, M, C, I, G = ("SOURCED", "SOURCED-VERIFY", "STANDARD", "DERIVED", "PROXY", "ANALOGUE",
                                   "MEASURED", "CALIBRATED", "ILLUSTRATIVE", "GAP")
IN = 0.0254
LB = 0.45359237

SOURCES = {
    "recon": "this reconstruction (design choices, see the notes)",
    # ---- machine
    "GM_MAN_EXP": "https://tehnikaplus.ru/upload/iblock/008/8w17q043yqsu37nbwiup2od3hbhif429.pdf - Gold Medal "
                  "'Econo Floss Export Model Series: 3017' manual (c) 2021, Part No. 110065, 28 pp., read in full "
                  "incl. photos p5/p20/p22; '220-230 V~, 50/60 Hz'",
    "GM_MAN_1997": "https://www.americanpartyrental.com/wp-content/uploads/2014/08/cotton-candy-machine.pdf - Econo-"
                   "Floss manual #3017 (1997, 120 V): 'Floss head rotates at 3450 RPM'",
    "GM_SHOP_3017": "https://shop.gmpopcorn.com/products/econo-floss-cotton-candy-machine-3017-00-000 - manufacturer "
                    "shop: \"26''w x 26''d x 17.15''h\", '1248' W, '31 lbs + Pan (11lbs.)', 'Up to 2-3 servings per minute'",
    "NM_SMARTGOODS": "https://www.smartgoods.de/neumaerker-zuckerwattemaschine-econo-floss-00-51551.html - retailer "
                     "copy of Neumaerker data: 'Grosse Aluminiumwanne O 650 mm inkl. Fangnetz', '230 V / 1080 W', "
                     "'660 x 660 x 440 mm', 'ca. 20 kg'",
    "GM42040_RETAIL": "https://popcornsupply.com/aluminum-metal-cotton-candy-pan ; https://www.partstown.com/p/gold-"
                      "medal-products/gldm42040 - snippets: '26\" Diameter x 9\" H', 'Floss Pan, 0.080 Alum 42040'",
    "GM3943_CFE": "https://www.cityfoodequipment.com/products/gold-medal-3943-double-bubble-cotton-candy-machine-"
                  "cover-clear - 'fits 26\" O.D. floss bowls', clear polyethylene",
    "GM3943_SMARTUK": "https://www.smartuk.net/candy-floss/gold-medal-clear-candy-floss-dome-3943/ - snippet: 660 mm",
    "PAT_US5766643": "https://patents.google.com/patent/US5766643A/en - Gold Medal 1998: perforated band, ribbon "
                     "heater, slip rings; 'fibers cool and collect on a mesh liner or a paper cone'",
    "PAT_US7300269": "https://patents.google.com/patent/US7300269B2/en - Gold Medal 2007: delay-on-break timer "
                     "'approximately 30 seconds'; sugar 'typically melts between 210 F. and 225 F.'; burns above 370 F",
    "PAT_US4872821": "https://patents.google.com/patent/US4872821A/en - Gold Medal 1989: slotted aluminium wall, "
                     "anodized dielectric coating, 'narrow ribbon of resistance wire wound in a flat coil'",
    "GGM_MAN": "https://static.ggmgastro.com/Cafe%20%26%20Eis/Zuckerwattemaschine/ZWET52/ZWET52%20Anleitung%20DE.pdf "
               "- GGM ZWET52 manual: 'Waermeleistung 1000 w', 'Motorleistung 80W', 'Produktion 1 / 30sek', "
               "'T Temperaturbegrenzer'",
    "PARAGON_WEB": "https://paragonconcessions.com/products/classic-floss-cotton-candy-machine - 'Motor: .0833 "
                   "Horsepower, 3400 RPM', 'Output: 200 cones per hour'",
    "BARTSCHER_DB": "https://www.zajadacz.de/documents/AZ_DB_B5_B5000.pdf - Bartscher B5000 datasheet 02/2024: "
                    "'Anschlusswert: 1,2 kW / 230 / 50/60 Hz', 'Messloeffel (12 -18 g)', 'O innen 500 mm'",
    "IEC_60335_2_9": "https://webstore.iec.ch/publication/61318 - snippet: scope of IEC 60335-2-9:2019 lists "
                     "'candy floss appliances'",
    # ---- ingredients / process
    "WIKI_SUC": "https://en.wikipedia.org/wiki/Sucrose - '1.587 g/cm3'; 'melts at approximately 189 C'",
    "ETB": "https://engineeringtoolbox.com/foods-materials-bulk-density-d_1819.html - snippet 'Sugar, granulated 800'",
    "SCHOKO": "https://www.schokomann.ch/schokoladenbrunnen-kaufen-schweiz/zuckerwatten-maschine/zuckerwatten-"
              "aromazucker.php - 'reicht fuer ca.50 Zuckerwatten'; 'Farbe Pink (E129)'; ingredients incl. lactose",
    "HOPSER": "https://hopser-funfood.de/1-KG-Vanille-Farbzucker-Aromazucker-fuer-Zuckerwatte-Bunt-"
              "Zuckerwattezucker - 'Ca. 50-80 Portionen je nach Dosierung'; 7.99-9.99 EUR/kg",
    "HOPSER_ST": "https://hopser-funfood.de/100-zuckerwattestaebe-40-cm-kiefernholz-4x4-mm-vierkantstaebe - "
                 "'Querschnitt: 4 x 4 mm Vierkant', 40 cm, Kiefernholz",
    "PCO": "https://www.pco-group.com/mnt/docs_shop/DE/5210003,5210004,5210017.ZuckerRotZuckerwatte.pdf - spec "
           "sheet 2019: 'Zucker, Aroma (Erdbeere), Farbstoff: E172'; 1698 kJ / 400 kcal per 100 g; 12 months",
    "WIESNKINI": "https://wiesnkini.de/magazin/wiesnpreisindex-wpi-2025/ - 'fuer eine kleine Zuckerwatte deren drei "
                 "(teilweise aber auch 2 EUR oder 2,50 EUR)'",
    "MARANO": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4866555/ - Marano et al., Eur J Pharm Biopharm 103:84 (2016): "
              "'aluminum spinneret (12.2 cm diameter)', '2400 rpm', 'Tg ... ~71', 'sucrose (mean value 9.77 um)'",
    "BANDI": "https://arxiv.org/pdf/2011.13642 - Bandi 2020: 'operate at temperatures around T = 160 - 175 C', "
             "'operate between 3000 - 4500 rpm', 'orifice dimensions of order 1-2 mm'",
    "PHYSW": "https://physicsworld.com/a/the-physics-of-candyfloss-on-earth-and-in-space/ - 'about 0.05 g/cm3', "
             "'around 190 C', 'about 50 um'",
    "LAB2004": "Labuza & Labuza, J Food Process Preserv 28(4):274 (2004), doi:10.1111/j.1745-4549.2004.24041.x - "
               "abstract: 0/11 % RH stable >= 12 months; 33 % RH collapse in 3 days; 45-75 % RH < 1 day",
    "ROE2005": "Roe & Labuza, Int J Food Prop 8(3):559 (2005) - abstract: amorphous sucrose Tg 60 C",
    "LEE2011": "Lee, Thomas, Schmidt, J Agric Food Chem 59:3306 (2011), doi:10.1021/jf104852u - DSC onset 184.1 C "
               "(secondary snippet)",
    "NATGEO": "https://www.nationalgeographic.com/culture/article/the-sticky-sweet-history-of-cotton-candy - "
              "'3,400 revolutions per minute', '50 microns'",
    "DEWIKI": "https://de.wikipedia.org/wiki/Zuckerwatte - 'drei bis sechs Gramm'",
    "GM_POUCH": "https://shop.gmpopcorn.com/products/o-jay-flossugar-pouches-3405 - '8-oz. pouch makes 8-10 cotton "
                "candy cones'",
    "PHOTO_FAIR": "public photos of fairground cotton candy portions (Kirmes / Oktoberfest) - visual scale against "
                  "hands and 40 cm sticks; not a measurement",
    # ---- booth / regulation
    "MH_PROFI": "https://www.markthuetten.de/ - '2 x 2 m Markthuette Basic', 'Theke innen mit 60cm Tiefe', "
                "'13 mm starken 3-Schicht-Platten'",
    "STEINHAUER": "https://www.steinhauer-holzhaus.de/Verkaufsstand/ - model table: Kent 4 ridge 210 cm; Nikolaus "
                  "gable 230 cm, 'Klappbare Fensterlaeden ... als praktische Theke'",
    "HUT_RENT": "kleinanzeigen / miet24 / verleih-er.de rental listings (search summary): 2 x 2 x 2.35 m hut; "
                "gable ca. 2.60 / standing height ca. 1.90",
    "CRAFTMAX": "craftmax.com food trailer pages (snippet): 'Masse Verkaufsklappe: 1.600 x 1.000 mm'",
    "COUNTER": "shopeinrichtung.com, kiosktheke.de (search summary): counter 90 (advice) / 95-100 / 105-110 cm",
    "ROLLS_STAND": "https://www.rolls-toys.de/shop/zuckerwatte-stand-mieten/ - 'Masse: 240 x 200 x 230 cm', red and "
                   "white nostalgic wooden stand",
    "CRYPTON": "https://www.crypton-event.de/eventmodule/zuckerwatte-stand/ - '2 x 2 x 3 m', '1 x 230 V/16 A'",
    "EU852": "https://gesetze.legal/eu/vo_eg_2004_852/anhang_ii - Reg. (EC) 852/2004 Annex II Ch. III",
    "MS_MB25": "https://www.stadt-muenster.de/fileadmin/user_upload/stadt-muenster/53_verbraucherschutz/pdf/"
               "mb_25_hygiene_an_verkaufsstaenden.pdf - Merkblatt (11/2020): 'Handwaschgelegenheit mit fliessendem "
               "Wasser, Einweghandtuechern und Einwegseife'",
    "LMZDV5": "https://www.buzer.de/5_LMZDV.htm - 'bei Lebensmitteln mit Farbstoffen durch die Angabe \"mit Farbstoff\"'",
    "EU1333_V": "https://gesetze.legal/eu/vo_eg_2008_1333/anhang_v - Reg. (EC) 1333/2008 Annex V: E110, E104, E122, "
                "E129, E102, E124 + 'Kann Aktivitaet und Aufmerksamkeit bei Kindern beeintraechtigen.'",
    "HN_FW": "https://feuerwehr.heilbronn.de - Merkblatt Brandschutz bei Maerkten und Strassenfesten (2022-02): "
             "'mindestens ein Feuerloescher', heat devices 0.50 m from combustibles or <= 85 C",
    "GEJA": "https://geja-event.de/wp-content/uploads/2026/02/Marktordnung-2026-final.pdf - '6 kg ABC- "
            "Feuerloescher', 'nur IP44, 57 und 65'",
    "HOCHSTADT": "https://www.weihnachtsmarkt-hochstadt.de/seite/524135/marktordnung.html - 'mit einem FI-"
                 "Schutzschalter fachmaennisch abzusichern'",
    "MBO76": "MBO par. 76 (2) via haufe.de (RP text): 'erdgeschossige Zelte und betretbare Verkaufsstaende ... bis zu "
             "einer Grundflaeche von 75 m2' need no Ausfuehrungsgenehmigung",
    "TSB_SAFETY": "https://cdn02.plentyone.com/zkz64ybyye6y/frontend/Artikel/Anleitungen/2026/teamsportbedarf-de_"
                  "Zelt-faltbar_Sicherheitshinweise_2026-03.pdf - 'mindestens 15 kg bis 25 kg pro Standbein'",
    "ASR_A12": "ASR A1.2 'Raumabmessungen und Bewegungsflaechen' 5.1 via https://vorschriften.bgn-branchenwissen.de/"
               "daten/tr/asr_a1_2/5.htm (search summary): Bewegungsflaeche >= 1,50 m2, Breite und Tiefe >= 1,00 m",
    "ASR_A18": "ASR A1.8 'Verkehrswege' 4.2 via https://www.komnet.nrw.de/_sitetools/dialog/22760 (search summary): "
               "lichte Hoehe ueber Verkehrswegen >= 2,00 m",
    "ZV_HANNOVER": "https://www.zeltverleih-hannover.de/mietzelte/verkaufsbuden/holzh%C3%BCtte-mit-verkaufsklappe-"
                   "leihen.html - snippet: hut 3.03 x 2.03 m, side wall 1.9 m, ridge 2.5 m",
    "PR2_URDF": "iai_pr2_description (~/ros_ws/src/iai_pr2) base_link collision box; PR2 base 668 mm square",
    "PR2_CRAM_CFG": "~/WORK/cognitive_robot_abstract_machine/semantic_digital_twin/src/semantic_digital_twin/robots/"
                    "pr2.py (collision rules: AvoidExternalCollisions buffer_zone_distance 0.1 default, 0.05 arms, "
                    "0.2 base_link with violated_distance 0.05) - read 2026-10-20",
    "WD_HUT": "https://wichtige-dinge.de/eventmodul/weihnachtsmarkthuette-buchen/ - hut 3.0 x 2.6 x 3.0 m, "
              "'Strom: 230V/16A', 'Inkl. Beleuchtung'",
    "DIN_EN631": "DIN EN 631-1 Gastronorm container sizes (GN 1/1 530 x 325 mm; GN 1/6 176 x 162 mm) - from "
                 "general knowledge of the standard, not re-read - VERIFY",
    "DIN33402": "DIN 33402-2:2020 body dimensions (adult elbow height standing ca. 1.0-1.15 m, 5th-95th pct.); "
                "values via secondary ergonomics tables - VERIFY",
}

P = {
    # ---------------------------------------------------------------- booth (wooden Markthuette, 3.0 x 2.6 m)
    "booth_width": (3.0, "m", S, "WD_HUT", "3.0 x 2.6 m market hut (ZV_HANNOVER rental 3.03 x 2.03 m); enlarged from the 2 x 2 m hut "
                    "(MH_PROFI, CRYPTON) on 2026-10-20 (user decision) because a PR2 does not fit 2 x 2 m with "
                    "collision-avoidance margins; Rolls-Toys Zuckerwatte stand 2.40 x 2.00 m (ROLLS_STAND)"),
    "booth_depth": (2.6, "m", S, "WD_HUT", "3.0 x 2.6 x 3.0 m market hut with 230 V/16 A; 2.0 m was too shallow for "
                    "a PR2 with its collision buffers (base 0.67 m + 2 x 0.20 m between machine table and back wall; "
                    "check C14, 2026-10-20)"),
    "booth_wall_panel_t": (0.013, "m", S, "MH_PROFI", "13 mm 3-ply Nordic spruce panels with frame"),
    "booth_roof_deck_t": (0.009, "m", S, "MH_PROFI", "9 mm screen-printed multiplex"),
    "booth_eave_height": (2.30, "m", I, "recon", "eave of the 3.0 m-high hut (not published); a 1.90 m operator "
                          "clears it, the sales-flap hinge sits below it"),
    "booth_ridge_height": (3.00, "m", S, "WD_HUT", "3.0 x 2.6 x 3.0 m market hut (the footprint used here); smaller "
                           "2 x 2 huts 2.30-2.60 (STEINHAUER, HUT_RENT) - with 2.5 m the PR2 torso could not rise "
                           "(mast in the roof buffer), so its shoulder stayed below the pan rim (2026-10-20)"),
    "booth_roof_overhang": (0.25, "m", I, "recon", "front and side overhang of the gable roof"),
    "booth_counter_depth": (0.60, "m", S, "MH_PROFI", "'Theke innen mit 60cm Tiefe'"),
    "booth_counter_height": (0.90, "m", PX, "COUNTER", "retail advice 90 cm (95-110 for checkout/gastro); low "
                             "enough that children see the machine"),
    "booth_counter_top_t": (0.027, "m", I, "recon", "solid wood worktop"),
    "booth_flap_width": (2.40, "m", I, "recon", "wide sales opening over machine and counter of the 3 m hut; trailer "
                         "flaps are 1600 x 1000 mm (CRAFTMAX)"),
    "booth_flap_height": (1.00, "m", A, "CRAFTMAX", "flap hinged at the top, opens up as a rain/sun awning"),
    "booth_flap_open_angle": (100.0, "deg", I, "recon", "rotation from the closed (hanging) position, held by gas "
                              "struts; edge rises above the hinge"),
    "booth_floor_height": (0.08, "m", I, "recon", "wooden floor on skids above the paving"),
    "booth_colour_scheme": ("pink/white", "-", I, "recon", "red-white nostalgic stands exist (ROLLS_STAND); no source "
                            "for pink Zuckerwatte livery -> GAP-driven design choice"),
    "booth_side_door_width": (0.70, "m", I, "recon", "rear-side entrance for the operator"),
    "machine_table_height": (0.62, "m", I, "recon", "lowered stainless machine table so the pan rim sits at elbow "
                             "height (checked in site/checks.py); a machine on the 0.90 m counter puts the rim at "
                             "1.34 m"),
    "handwash_unit": ((0.45, 0.45, 0.85), "m", A, "MS_MB25", "mobile hand-wash station with fresh/waste water "
                      "canisters, typical market-trader unit; dimensions illustrative"),
    "robot_base_footprint": (0.668, "m", PX, "PR2_URDF", "PR2 base square edge; MEASURED from the parked robot in "
                             "the CRAM world -> data/robot_envelope.json when available"),
    "robot_buffer_base": (0.20, "m", S, "PR2_CRAM_CFG", "giskard buffer zone of base_link (violated below 0.05 m)"),
    "robot_buffer_arm": (0.05, "m", S, "PR2_CRAM_CFG", "buffer zone of the arm links (end effectors excluded)"),
    "robot_buffer_base_booth": (0.08, "m", I, "recon", "base_link buffer used in the booth (CRAM default 0.20 m keeps "
                                "the spinner head ~0.88 m from the shoulder, beyond reliable PR2 reach) - tight-"
                                "workplace tuning, applied as an extra collision rule in the CRAM world"),
    "robot_violated_base_booth": (0.03, "m", I, "recon", "base_link violated distance in the booth (CRAM default 0.05)"),
    "robot_buffer_default": (0.10, "m", S, "PR2_CRAM_CFG", "buffer zone of all other robot links"),
    "gn16_size": ((0.176, 0.162), "m", SV, "DIN_EN631", "Gastronorm 1/6 container 176 x 162 mm"),
    "side_shelf_depth": (0.30, "m", I, "recon", "3-level shelf on the right wall (sugar tubs, sticks, bag stock)"),
    # ---------------------------------------------------------------- booth regulation / equipment
    "reg_fliegende_bauten_limit": (75.0, "m2", ST, "MBO76", "sales stands up to 75 m2 need no Ausfuehrungs-"
                                   "genehmigung (MBO par. 76(2)); this booth is 4 m2"),
    "reg_handwash_required": (True, "-", ST, "MS_MB25", "loose food (except fresh fruit/veg): hand wash with running "
                              "water, disposable towels and soap; EU852 Annex II Ch. III 2(a)"),
    "reg_colour_label": ("mit Farbstoff", "-", ST, "LMZDV5", "par. 5(1) Nr. 1 LMZDV for loose goods with colours"),
    "reg_azo_warning": ("E129: Kann Aktivitaet und Aufmerksamkeit bei Kindern beeintraechtigen.", "-", ST, "EU1333_V",
                        "Annex V, needed because the pink sugar uses E129 (Allura Red)"),
    "reg_allergen_lactose": (True, "-", S, "SCHOKO", "coloured floss sugar contains lactose -> milk allergen "
                             "information for loose goods (LMIV Art. 9(1)c / 44)"),
    "reg_fire_extinguisher_kg": (6.0, "kg", S, "GEJA", "6 kg ABC powder extinguisher per stand (EN 3)"),
    "reg_heat_clearance": (0.50, "m", S, "HN_FW", "heating devices 0.50 m from combustibles, or surfaces stay <= 85 C"),
    "reg_rcd_required": (True, "-", S, "HOCHSTADT", "supply protected by an RCD (FI); 30 mA per VDE 0100-711 (VERIFY)"),
    "el_supply_voltage": (230.0, "V", S, "CRYPTON", "1 x 230 V / 16 A typical stand connection"),
    "el_supply_current": (16.0, "A", S, "CRYPTON", "Schuko / CEE 16 A"),
    "el_led_lighting_w": (60.0, "W", I, "recon", "LED strip under the eave + illuminated sign"),
    "el_sign_w": (25.0, "W", I, "recon", "LED-backlit 'Zuckerwatte' sign"),
    # ---------------------------------------------------------------- machine: cabinet
    "m_power_230": (1080.0, "W", SV, "NM_SMARTGOODS", "'230 V / 1080 W'; GM 120 V model 1248 W (GM_SHOP_3017)"),
    "m_motor_power": (80.0, "W", PX, "GGM_MAN", "GGM ZWET52 'Motorleistung 80W'; Paragon 1/12 hp = 62 W; GM motor "
                      "48649EX power not published"),
    "m_heater_power": (1000.0, "W", D, "recon", "m_power_230 - m_motor_power (weakest input PROXY)"),
    "m_overall_width": (0.6604, "m", S, "GM_SHOP_3017", "26 in incl. pan; Neumaerker 660 mm"),
    "m_overall_height": (0.4356, "m", S, "GM_SHOP_3017", "17.15 in incl. pan; listings 17-20 in (+-50 mm)"),
    "m_mass": (14.1, "kg", S, "GM_SHOP_3017", "31 lb machine; pan + 11 lb shipping; Neumaerker 'ca. 20 kg' incl. pan"),
    "m_feet_height": (0.019, "m", S, "GM_MAN_EXP", "4 rubber feet, 3/4 in (part 47155)"),
    "m_cabinet_height": (0.188, "m", D, "recon", "m_overall_height - m_feet_height - pan_height = 436-19-229 mm; "
                         "matches the photo proportion (GM_MAN_EXP p20)"),
    "m_cabinet_width": (0.36, "m", A, "GM_MAN_EXP", "scaled from photo p20: front ~2.6x band diameter"),
    "m_cabinet_depth": (0.33, "m", A, "GM_MAN_EXP", "scaled from photo p5/p20"),
    "m_cabinet_material": ("brushed stainless", "-", S, "GM_SHOP_3017", "'Stainless steel cabinet design'"),
    "m_front_panel_colour": ("blue, pink heat dial", "-", A, "GM_MAN_EXP", "photos p5/p20: blue front label, pink "
                             "graduated ring around the black heat knob; brand lettering replaced by generic text"),
    "m_switch_motor": ("Motor & Master, lighted rocker", "-", S, "GM_MAN_EXP", "'turns Motor ON/OFF and supplies "
                       "power to the Heat Switch'"),
    "m_switch_heat": ("Heat, lighted rocker", "-", S, "GM_MAN_EXP", "'turns the heating element ON/OFF'"),
    "m_heat_knob_range": (270.0, "deg", I, "recon", "1000 ohm potentiometer 55332 (GM_MAN_EXP); rotation range not "
                          "published, 270 deg is the usual pot travel"),
    "m_lockngo_angle": (90.0, "deg", S, "GM_MAN_EXP", "p5: handles rotate from LOCKED (transport) to UNLOCKED; "
                        "'DO NOT operate with handles in the transport position'"),
    "m_suspension": ("bell housing on springs", "-", S, "GM_MAN_EXP", "'float freely on the springs for operation' "
                     "(springs 42524)"),
    "m_suspension_travel": (0.006, "m", I, "recon", "spring float of the bell housing, not published"),
    "m_bell_diameter": (0.18, "m", A, "GM_MAN_EXP", "aluminium bell housing, photo p20 ~1.3x band diameter"),
    "m_bell_height": (0.10, "m", A, "GM_MAN_EXP", "photo p20"),
    # ---------------------------------------------------------------- machine: pan, stabilizer, bubble
    "pan_inner_diameter": (26 * IN, "m", SV, "GM42040_RETAIL", "'inside diameter: 26\"'; Neumaerker 650 mm"),
    "pan_outer_diameter": (26.5 * IN, "m", SV, "GM42040_RETAIL", "26.5 in rim"),
    "pan_height": (9 * IN, "m", SV, "GM42040_RETAIL", "9 in"),
    "pan_wall_t": (0.080 * IN, "m", SV, "GM_MAN_EXP", "'Floss Pan, 0.080 Alum 42040'"),
    "pan_material": ("spun aluminium", "-", SV, "GM42040_RETAIL", "option: non-metallic pan"),
    "pan_mass": (3.1, "kg", SV, "GM42040_RETAIL", "6.75 lb (another listing 10 lb)"),
    "stabilizer_height": (0.16, "m", I, "recon", "plastic screening hung from rim clips, 'about flush with top of "
                          "pan' (GM_MAN_EXP p6); height not published"),
    "stabilizer_gap": (0.025, "m", I, "recon", "'Allow air space between pan and screening' (GM_MAN_EXP)"),
    "stabilizer_clips": (6, "-", SV, "GM_MAN_EXP", "clip count varies by model; KaTom lists 6"),
    "bubble_base_diameter": (26.5 * IN, "m", PX, "GM3943_CFE", "'fits 26\" O.D. floss bowls'"),
    "bubble_height": (0.50, "m", PX, "GM3943_SMARTUK", "listing says 660 mm (probably box size); 0.50 m chosen so "
                      "the operator can reach in through the front opening"),
    "bubble_opening_angle": (150.0, "deg", I, "recon", "front cut-out of the dome for the operator; 110 deg blocked "
                             "a PR2 forearm coming in diagonally from beside the machine (kinematic test 2026-10-20)"),
    # ---------------------------------------------------------------- machine: spinner head
    "head_band_diameter": (5.5 * IN, "m", S, "GM_MAN_EXP", "'5 1/2 FLOSS BAND 43165' = head outer diameter"),
    "head_band_height": (0.034, "m", A, "GM_MAN_EXP", "photo p22 scaled by band diameter"),
    "head_cap_height": (0.065, "m", A, "GM_MAN_EXP", "conical spinner cap 43166, photo p22"),
    "head_cap_top_diameter": (0.060, "m", A, "GM_MAN_EXP", "sugar inlet at the top of the cap, photo p22"),
    "head_slot_count": (36, "-", A, "GM_MAN_EXP", "slanted slots counted on photo p22 (~18 visible on the front half)"),
    "head_slot_angle": (35.0, "deg", A, "GM_MAN_EXP", "slot inclination, photo p5 close-up"),
    "head_slot_width": (0.003, "m", A, "GM_MAN_EXP", "photo p5 close-up; commercial orifices 1-2 mm (BANDI)"),
    "head_rpm": (3450.0, "rpm", S, "GM_MAN_1997", "'Floss head rotates at 3450 RPM' (60 Hz); 50 Hz speed GAP"),
    "head_rpm_50hz": (2875.0, "rpm", D, "recon", "3450 x 50/60 for a 60 Hz induction-motor speed (assumes no gear); "
                      "range 3100-3450 in other machines (GGM, PARAGON)"),
    "head_floaters": (2, "-", S, "GM_MAN_EXP", "leather floaters 20010 on the cap lift floss up the pan wall"),
    "head_slip_rings": (2, "-", S, "GM_MAN_EXP", "slip rings 42126HD + carbon brushes 55007"),
    "head_fill_fraction": (0.90, "-", S, "GM_MAN_EXP", "'fill head 90% full ... necessary to obtain a balanced "
                           "condition'"),
    "head_sugar_capacity": (0.060, "kg", C, "GM_SHOP_3017", "absolute capacity not published (GAP); CALIBRATED so "
                            "one fill (90 %) lasts ~1 min at the rated 2-3 servings/min - a 25 g head would force a "
                            "stop/refill/35 s warm-up after every portion, contradicting the rated output"),
    "head_ribbon": ("nickel-wire flat-coil ribbon", "-", S, "GM_MAN_EXP", "'Floss Ribbons (heat elements) are made "
                    "of nickel wire'; export head uses double ribbon"),
    "head_band_coating": ("anodized aluminium, slotted", "-", S, "PAT_US4872821", "slotted aluminium wall with "
                          "anodized dielectric coating"),
    # ---------------------------------------------------------------- machine: operation
    "op_master_to_heat_delay": (10.0, "s", S, "GM_MAN_EXP", "'Turn the Motor & Master Switch ON. Wait 10 seconds'"),
    "op_warmup": (25.0, "s", S, "GM_MAN_EXP", "'start making floss in about 20-30 seconds' at max heat; "
                  "GGM 4-5 min (other design)"),
    "op_output_rate": (2.5, "servings/min", S, "GM_SHOP_3017", "'Up to 2-3 servings per minute'"),
    "op_run_after_heat_off": (30.0, "s", S, "PAT_US7300269", "delay-on-break ~30 s (15-60 s) to clear the head"),
    "op_burnout_clean_min": (3.5, "min", S, "GM_MAN_EXP", "run empty at max heat 3-4 min, then motor only 1-2 min; "
                             "'NEVER put water in the floss head'"),
    "op_ambient_min": (5.0, "C", S, "GM_MAN_EXP", "5-55 C operating ambient"),
    "op_ambient_max": (55.0, "C", S, "GM_MAN_EXP", ""),
    "op_clean_brushes_every": (500 * LB, "kg sugar", S, "GM_MAN_EXP", "'CLEAN EVERY 500 LBS'"),
    # ---------------------------------------------------------------- sugar / ingredients
    "sucrose_density": (1587.0, "kg/m3", S, "WIKI_SUC", "crystal density; Engineering ToolBox 1550"),
    "sugar_bulk_density": (800.0, "kg/m3", SV, "ETB", "granulated; loose 850 / tapped 950 elsewhere"),
    "sucrose_melt": (186.0, "C", SV, "LEE2011", "DSC onset 184.1 C; Wikipedia ~189; GM patent '210-225 F' (99-107 C) "
                     "contradicts physical data -> not used"),
    "sucrose_burn": (188.0, "C", S, "PAT_US7300269", "'burns at temperatures above 370 F'"),
    "head_melt_temp": (170.0, "C", SV, "BANDI", "band/ribbon zone: 160-175 C typical; other sources 190-210 C"),
    "sucrose_tg_dry": (60.0, "C", S, "ROE2005", "amorphous sucrose; spun fibres ~71 C (MARANO)"),
    "floss_stable_rh": (11.0, "%RH", S, "LAB2004", "0 and 11 % RH stable >= 12 months at 25 C"),
    "floss_collapse_rh": (33.0, "%RH", S, "LAB2004", "33 % RH: collapse + crystallisation within 3 days"),
    "floss_collapse_days_33": (3.0, "d", S, "LAB2004", ""),
    "floss_collapse_days_45": (1.0, "d", S, "LAB2004", "45, 54, 75 % RH: < 1 day (upper bound used)"),
    "fibre_diameter": (10e-6, "m", S, "MARANO", "lab sucrose spinner 9.77 um; popular '50 um' (NATGEO) not measured"),
    "portion_sugar": (0.020, "kg", S, "SCHOKO", "1 kg ~ 50 portions; HOPSER 12.5-20 g; DEWIKI 3-6 g (home); "
                      "GM 23-28 g"),
    "portion_diameter": (0.28, "m", A, "PHOTO_FAIR", "typical fair portion on a 40 cm stick, ~ shoulder width of a "
                         "child; no sourced measurement (GAP)"),
    "portion_length": (0.24, "m", A, "PHOTO_FAIR", "along the stick"),
    "floss_density_physw": (50.0, "kg/m3", S, "PHYSW", "'about 0.05 g/cm3' - inconsistent with portion size: 20 g "
                            "would be a 9 cm ball; probably a compressed-floss value, not used for geometry"),
    "floss_bulk_density": (2.0, "kg/m3", D, "recon", "portion_sugar / ellipsoid(portion_diameter, portion_length) "
                           "-> weakest input ANALOGUE"),
    "colour_sugar_pink": ("sugar, silica E551, lactose, colour E129, flavour", "-", S, "SCHOKO", "pink 'Himbeer' "
                          "Farbzucker; blue uses E133"),
    "colour_sugar_energy": (400.0, "kcal/100g", S, "PCO", "1698 kJ"),
    "colour_sugar_price": (8.99, "EUR/kg", S, "HOPSER", "7.99-9.99 EUR/kg retail"),
    "colour_sugar_shelf_life": (12.0, "months", S, "PCO", "store dry, room temperature"),
    "sugar_carton": ("half-gallon Flossugar carton with E-Z pour spout", "-", S, "GM_MAN_EXP",
                     "'packed in handy half-gallon sealed cartons, with an E-Z pour spout for filling your machine' "
                     "(p. 9); the robot fills the head from the carton (reach over the 0.66 m pan)"),
    "sugar_carton_size": ((0.095, 0.095, 0.195), "m", A, "recon", "US half-gallon gable-top carton ~3.75 x 3.75 x "
                          "7.7 in (milk carton analogue); spout on top"),
    "sugar_carton_grip_height": (0.03, "m", I, "recon", "grip just above the carton bottom so the tilted spout reaches "
                                 "~0.17 m ahead of the gripper"),
    "sugar_tub_volume": (0.010, "m3", I, "recon", "10 L lidded food-grade tub per colour (white, pink, blue)"),
    "scoop_volume": (25e-6, "m3", D, "recon", "portion_sugar / sugar_bulk_density = 25 mL scoop"),
    "stick_length": (0.40, "m", S, "HOPSER_ST", "pine wood, food grade"),
    "stick_section": (0.004, "m", S, "HOPSER_ST", "4 x 4 mm square"),
    "stick_bundle": (100, "-", S, "HOPSER_ST", "pack of 100"),
    "bag_width": (0.30, "m", I, "recon", "'12 x 18' listing without unit (EBAY) -> 12 x 18 in ~ 0.30 x 0.46 m"),
    "bag_height": (0.46, "m", I, "recon", ""),
    "price_portion": (3.0, "EUR", S, "WIESNKINI", "small portion Oktoberfest 2025: 3 EUR (some 2-2.50)"),
    # ---------------------------------------------------------------- operator / ergonomics
    "op_elbow_height": (1.05, "m", SV, "DIN33402", "adult standing elbow height ~1.0-1.15 m; winding happens "
                        "just above the pan rim"),
    "op_rim_above_elbow_max": (0.10, "m", I, "recon", "winding happens at/just above the pan rim: rim <= elbow + 0.10"),
    "op_rim_below_elbow_max": (0.25, "m", I, "recon", "rim no lower than elbow - 0.25 (no deep stooping)"),
    "asr_move_area": (1.50, "m2", SV, "ASR_A12", "free movement area at the workplace; applies to the operator"),
    "asr_move_width": (1.00, "m", SV, "ASR_A12", "min. width and depth of the movement area (standing work)"),
    "asr_headroom": (2.00, "m", SV, "ASR_A18", "clear height over traffic routes; used for the open flap above "
                     "customers (a market stall is not a building; applied as a design rule)"),
    # ---------------------------------------------------------------- environment
    "env_surface": ("concrete pavers", "-", I, "recon", "fair squares are paved/asphalt (MS_MB25 requires solid floor)"),
    "env_rh": (60.0, "%RH", I, "recon", "German autumn evening; drives the floss collapse model"),
    "env_temp": (12.0, "C", I, "recon", "autumn evening fair"),
}


def get(key):
    v = P[key]
    if v[0] is None:
        raise KeyError(f"{key} is a GAP - no value may be invented in code")
    return v[0]


def status_counts(entries=None):
    return Counter(v[2] for v in (entries or P).values())


def audit():
    ok = True
    for k, v in P.items():
        for src in v[3].split(";"):
            if src.strip() not in SOURCES:
                print(f"FAIL source key {src!r} of {k} not in SOURCES")
                ok = False
    return ok


if __name__ == "__main__":
    w = max([len(k) for k in P] + [3])
    for k, (v, u, s, src, note) in P.items():
        vs = f"{v:.4g}" if isinstance(v, float) else str(v)
        print(f"{k:<{w}}  {vs[:28]:>28} {u:<12} {s:<15} {src:<15} {note[:90]}")
    n = len(P) or 1
    print(f"\n{len(P)} entries: " + "  ".join(f"{s} {c} ({100 * c / n:.0f} %)"
                                              for s, c in status_counts().most_common()))
    sys.exit(0 if audit() else 1)
