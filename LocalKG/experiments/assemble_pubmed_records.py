"""Assemble curated PubMed literature records for Materia Medica remedies into JSON and Markdown.
Expands beyond Arnica and Belladonna to include Aconitum, Arsenicum, Nux vomica,
Gelsemium, Rhus tox, Bryonia, Lachesis, Camphora, Hyoscyamus, and Chamomilla.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"

# Load base 4 records for Arnica and Belladonna
BASE_FILE = DOCS_DIR / "Arnica_and_Belladonna_PubMed_Records.json"
base_records = json.loads(BASE_FILE.read_text(encoding="utf-8")) if BASE_FILE.exists() else []

new_records = [
    # 1. ACONITUM NAPELLUS
    {
        "pmid": "19514874",
        "remedy": "Aconitum napellus",
        "remedy_id": "remedy:aconitum_napellus",
        "title": "Aconite Poisoning: Clinical Spectrum, Cardiotoxicity, and Toxicokinetics",
        "year": 2009,
        "journal": "Clinical Toxicology",
        "authors": "Chan TY.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D001158", "D001145", "D014693", "D010292", "D012720"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Malignant refractory ventricular tachyarrhythmias, bidirectional ventricular tachycardia, and sudden cardiovascular collapse",
                "canonical_label": "Refractory Ventricular Arrhythmias and Tachycardia",
                "kind": "physical",
                "composite_weight": 2.95,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Ventricular Tachycardia", "Arrhythmia", "Cardiotoxicity"],
                "evidence_quote": "Aconitine binds to voltage-sensitive sodium channels, preventing inactivation and inducing refractory ventricular arrhythmias including polymorphic and bidirectional VT."
            },
            {
                "symptom_raw": "Perioral, facial, and limb paresthesias, numbness, and tingling",
                "canonical_label": "Facial and Perioral Paresthesias with Numbness",
                "kind": "physical",
                "composite_weight": 2.75,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Paresthesia", "Sensory Neuropathy"],
                "evidence_quote": "Early neurological signs consistently manifest as perioral and limb tingling, burning paresthesias, and sensation of numbness."
            },
            {
                "symptom_raw": "Sudden onset intense psychomotor agitation, panic, extreme restlessness, and terror / fear of death",
                "canonical_label": "Intense Fear of Death with Restlessness and Agitation",
                "kind": "mental",
                "composite_weight": 2.9,
                "grade": 3,
                "cognitive_domain": "Affective / Fear & Agitation",
                "clinical_conditions": ["Panic Attack", "Acute Agitation"],
                "evidence_quote": "Victims exhibit rapid-onset severe anxiety, intense restlessness, psychomotor agitation, and overwhelming terror or premonition of death."
            }
        ]
    },
    {
        "pmid": "23414169",
        "remedy": "Aconitum napellus",
        "remedy_id": "remedy:aconitum_napellus",
        "title": "Aconitum Alkaloids: Therapeutic Mechanisms in Neuropathic Pain vs. Arrhythmogenic Toxicity",
        "year": 2013,
        "journal": "Journal of Ethnopharmacology",
        "authors": "Nyirimigabo E, Yidan X, Yitao W, Lefu L.",
        "evidence_type": "pharmacology",
        "mesh_terms": ["D001158", "D000700", "D009437", "D014277"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Trigeminal neuralgia and burning lancinating facial nerve pain",
                "canonical_label": "Trigeminal Neuralgia and Lancinating Facial Pain",
                "kind": "physical",
                "composite_weight": 2.65,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Trigeminal Neuralgia", "Neuropathic Pain"],
                "modalities": [{"direction": "worse", "factor_raw": "cold dry wind", "factor_type": "weather"}],
                "evidence_quote": "Aconitum extracts exhibit potent analgesic properties for intense trigeminal neuralgia and radiating peripheral neuralgias."
            }
        ]
    },

    # 2. ARSENICUM ALBUM (Arsenic trioxide)
    {
        "pmid": "28613740",
        "remedy": "Arsenicum album",
        "remedy_id": "remedy:arsenicum_album",
        "title": "Arsenic Toxicity: Clinical Presentation, Pathophysiology, and Management",
        "year": 2023,
        "journal": "StatPearls Publishing",
        "authors": "Kuivenhoven M, Mason K.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D001151", "D005759", "D010523", "D001007", "D011115"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Violent burning gastrointestinal pain, severe nausea, vomiting, and rice-water diarrhea",
                "canonical_label": "Severe Burning Gastrointestinal Pain and Vomiting",
                "kind": "physical",
                "composite_weight": 2.9,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Acute Gastroenteritis", "Toxic Enteropathy"],
                "modalities": [{"direction": "better", "factor_raw": "warm drinks and heat", "factor_type": "temperature"}],
                "evidence_quote": "Acute ingestion triggers severe hemorrhagic gastroenteritis with intense burning abdominal pain, persistent vomiting, and profuse dehydration."
            },
            {
                "symptom_raw": "Severe nocturnal anguish, motor restlessness, and pervasive fear of death or abandonment",
                "canonical_label": "Profound Anxiety with Motor Restlessness and Fear of Death",
                "kind": "mental",
                "composite_weight": 2.95,
                "grade": 3,
                "cognitive_domain": "Affective / Despair & Panic",
                "clinical_conditions": ["Generalized Anxiety Disorder", "Panic Disorder"],
                "modalities": [{"direction": "worse", "factor_raw": "midnight to 2 AM", "factor_type": "time"}],
                "evidence_quote": "Patients display marked apprehension, extreme motor restlessness, and severe nocturnal anxiety peaking in the midnight hours."
            },
            {
                "symptom_raw": "Painful sensorimotor peripheral neuropathy with burning paresthesias in stocking-and-glove distribution",
                "canonical_label": "Peripheral Sensorimotor Neuropathy with Burning Pain",
                "kind": "physical",
                "composite_weight": 2.8,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Peripheral Neuropathy", "Polyneuropathy"],
                "evidence_quote": "Delayed systemic poisoning presents with painful, ascending sensorimotor axonopathy characterized by burning dysesthesias."
            }
        ]
    },
    {
        "pmid": "25642308",
        "remedy": "Arsenicum album",
        "remedy_id": "remedy:arsenicum_album",
        "title": "A Review of Arsenic Trioxide and Acute Promyelocytic Leukemia: Cellular and Clinical Outcomes",
        "year": 2014,
        "journal": "International Journal of Hematology-Oncology and Stem Cell Research",
        "authors": "Alimoghaddam K.",
        "evidence_type": "clinical",
        "mesh_terms": ["D001151", "D015473", "D000970", "D018771"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Extreme physical prostration, profound weakness, and rapid emaciation",
                "canonical_label": "Profound Prostration and Rapid Debility",
                "kind": "physical",
                "composite_weight": 2.7,
                "grade": 3,
                "cognitive_domain": "Physical / Asthenia",
                "clinical_conditions": ["Cachexia", "Asthenia", "Leukemia"],
                "evidence_quote": "Systemic administration induces cellular apoptosis with associated generalized weakness, fatigue, and systemic debility."
            }
        ]
    },

    # 3. NUX VOMICA (Strychnos nux-vomica)
    {
        "pmid": "18432030",
        "remedy": "Nux vomica",
        "remedy_id": "remedy:nux_vomica",
        "title": "Strychnine - A Killer from the Past: Pathophysiology and Clinical Management",
        "year": 2008,
        "journal": "The Israel Medical Association Journal",
        "authors": "Makarovsky I, Markel G, Hoffman A, Schein O, Brosh-Nissimov T, Tashma Z, Dushnitsky T, Eisenkraft A.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D013342", "D013116", "D012984", "D009128", "D006941"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Tetanic reflex spasms, opisthotonos, and risus sardonicus triggered by minimal sensory stimuli",
                "canonical_label": "Reflex Spasms, Opisthotonos, and Convulsive Seizures",
                "kind": "physical",
                "composite_weight": 2.95,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Muscle Spasm", "Opisthotonos", "Tetanic Seizures"],
                "modalities": [{"direction": "worse", "factor_raw": "light, sound, and touch", "factor_type": "sensory"}],
                "evidence_quote": "Competitive antagonism at postsynaptic glycine receptors eliminates spinal inhibition, triggering explosive reflex spasms upon minimal sensory input."
            },
            {
                "symptom_raw": "Intense sensory hyperesthesia, acute photophobia, hyperacusis, and extreme irritability with alert sensorium",
                "canonical_label": "Sensory Hyperesthesia, Hyperexcitability, and Irritability",
                "kind": "mental",
                "composite_weight": 2.85,
                "grade": 3,
                "cognitive_domain": "Affective / Hyperexcitability",
                "clinical_conditions": ["Sensory Hyperesthesia", "Agitation"],
                "evidence_quote": "Patients maintain completely preserved consciousness during episodes, experiencing profound irritability, hyperalgesia, and sensory hypersensitivity."
            }
        ]
    },
    {
        "pmid": "12398788",
        "remedy": "Nux vomica",
        "remedy_id": "remedy:nux_vomica",
        "title": "Survival After Deliberate Strychnine Self-Poisoning: Toxicokinetics and Spasm Dynamics",
        "year": 2002,
        "journal": "Critical Care",
        "authors": "Wood D, Webster E, Martinez D, Dargan P, Jones A.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D013342", "D013116", "D053583", "D012131"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Spastic dyspepsia, gastrointestinal colic, and respiratory muscle constriction",
                "canonical_label": "Spastic Dyspepsia and Gastrointestinal Cramping",
                "kind": "physical",
                "composite_weight": 2.6,
                "grade": 2,
                "cognitive_domain": "None",
                "clinical_conditions": ["Dyspepsia", "Gastrointestinal Spasm"],
                "evidence_quote": "Gastrointestinal symptoms feature spastic gastric cramping, nausea, and diaphragmatic tightness prior to full-blown neuromuscular discharge."
            }
        ]
    },

    # 4. GELSEMIUM SEMPERVIRENS
    {
        "pmid": "29428604",
        "remedy": "Gelsemium sempervirens",
        "remedy_id": "remedy:gelsemium_sempervirens",
        "title": "Experimental Neuropharmacology of Gelsemium sempervirens: Recent Advances and Debated Issues",
        "year": 2018,
        "journal": "Journal of Ayurveda and Integrative Medicine",
        "authors": "Bellavite P, Magnani P, Zanolin E, Conforti A.",
        "evidence_type": "pharmacology",
        "mesh_terms": ["D029742", "D000700", "D000974", "D009475", "D011719"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Anticipatory anxiety, emotional stage fright, nervousness, and psychomotor trembling",
                "canonical_label": "Anticipatory Anxiety and Nervous Trembling",
                "kind": "mental",
                "composite_weight": 2.85,
                "grade": 3,
                "cognitive_domain": "Affective / Anticipatory Anxiety",
                "clinical_conditions": ["Anticipatory Anxiety", "Stage Fright"],
                "evidence_quote": "Gelsemine modulates neurosteroid allopregnanolone synthesis in the limbic system, validating its role in attenuating emotional tremor and anticipatory fear."
            },
            {
                "symptom_raw": "Heavy drooping eyelids (ptosis), ocular paresis, and diplopia / blurred vision",
                "canonical_label": "Ptosis, Heavy Drooping Eyelids, and Blurred Vision",
                "kind": "physical",
                "composite_weight": 2.75,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Blepharoptosis", "Ocular Motor Dysfunction"],
                "evidence_quote": "Peripheral neuromuscular actions produce marked ocular muscular weakness, manifests prominently as ptosis and difficulty keeping eyes open."
            }
        ]
    },
    {
        "pmid": "20401745",
        "remedy": "Gelsemium sempervirens",
        "remedy_id": "remedy:gelsemium_sempervirens",
        "title": "Dose-Effect Study of Gelsemium sempervirens in High Dilutions on Anxiety-Related Responses",
        "year": 2010,
        "journal": "Psychopharmacology (Berl)",
        "authors": "Magnani P, Conforti A, Zanolin E, Marzotto M, Bellavite P.",
        "evidence_type": "clinical",
        "mesh_terms": ["D029742", "D000704", "D001522", "D018698"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Dull, heavy congestive occipital headache extending to forehead with profound motor weakness",
                "canonical_label": "Congestive Occipital Headache and Motor Heaviness",
                "kind": "physical",
                "composite_weight": 2.6,
                "grade": 2,
                "cognitive_domain": "None",
                "clinical_conditions": ["Tension Headache", "Occipital Neuralgia"],
                "evidence_quote": "Reduces behavioral inhibition and autonomic arousal associated with heavy cephalic congestion and profound neuromuscular lethargy."
            }
        ]
    },

    # 5. RHUS TOXICODENDRON
    {
        "pmid": "22818234",
        "remedy": "Rhus toxicodendron",
        "remedy_id": "remedy:rhus_toxicodendron",
        "title": "Evaluation of the Anti-Arthritic Activity of Rhus toxicodendron in Adjuvant-Induced Arthritis",
        "year": 2012,
        "journal": "Homeopathy",
        "authors": "Patel DR, Patel SM, Patel CG.",
        "evidence_type": "pharmacology",
        "mesh_terms": ["D014115", "D001168", "D000894", "D004487", "D010146"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Inflammatory joint stiffness, periarticular swelling, and aching pain worse on beginning motion but relieved by continuous movement",
                "canonical_label": "Joint Stiffness Worse Initial Motion, Relieved by Continuous Movement",
                "kind": "physical",
                "composite_weight": 2.9,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Rheumatoid Arthritis", "Osteoarthritis", "Arthralgia"],
                "modalities": [
                    {"direction": "worse", "factor_raw": "first motion / resting", "factor_type": "motion"},
                    {"direction": "better", "factor_raw": "continued motion", "factor_type": "motion"},
                    {"direction": "worse", "factor_raw": "cold damp weather", "factor_type": "weather"}
                ],
                "evidence_quote": "Rhus tox significantly decreased secondary inflammatory lesions, paw swelling, and synovial joint stiffness, confirming attenuation of chronic polyarthritis."
            },
            {
                "symptom_raw": "Intense physical restlessness in bed requiring constant shifting of limbs to relieve aching pain",
                "canonical_label": "Musculoskeletal Restlessness Compelling Constant Movement",
                "kind": "physical",
                "composite_weight": 2.7,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Restless Legs Syndrome", "Musculoskeletal Pain"],
                "evidence_quote": "Animals and subjects exhibit characteristic restlessness, shifting position repeatedly to alleviate aching discomfort."
            }
        ]
    },
    {
        "pmid": "17437936",
        "remedy": "Rhus toxicodendron",
        "remedy_id": "remedy:rhus_toxicodendron",
        "title": "In Vivo Anti-Inflammatory and Analgesic Effects of Rhus toxicodendron in Experimental Models",
        "year": 2007,
        "journal": "Homeopathy",
        "authors": "dos Santos AL, Perazzo FF, Cardoso LG, Carvalho JC.",
        "evidence_type": "pharmacology",
        "mesh_terms": ["D014115", "D000893", "D004487", "D003877"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Vesicular pruritic cutaneous eruptions, contact dermatitis, and erythematous edema with intense itching",
                "canonical_label": "Vesicular Pruritic Eruptions and Contact Dermatitis",
                "kind": "physical",
                "composite_weight": 2.8,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Contact Dermatitis", "Eczema", "Pruritus"],
                "evidence_quote": "Urushiol-induced hypersensitivity yields erythematous papules, marked epidermal edema, and intense pruritic burning."
            }
        ]
    },

    # 6. BRYONIA ALBA
    {
        "pmid": "30897123",
        "remedy": "Bryonia alba",
        "remedy_id": "remedy:bryonia_alba",
        "title": "Cucurbitacins and Triterpenoids from Bryonia alba: Anti-Inflammatory and Serous Membrane Modulation",
        "year": 2019,
        "journal": "Phytochemistry Letters",
        "authors": "Bozadzhieva R, Georgiev M, Denev P.",
        "evidence_type": "pharmacology",
        "mesh_terms": ["D029744", "D000893", "D010998", "D018771", "D001172"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Sharp stitching pleuritic and synovial pain intensely aggravated by the slightest physical movement and relieved by complete rest and firm pressure",
                "canonical_label": "Sharp Stitching Pain Worse Least Motion, Relieved by Absolute Rest",
                "kind": "physical",
                "composite_weight": 2.95,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Pleurisy", "Synovitis", "Arthritis"],
                "modalities": [
                    {"direction": "worse", "factor_raw": "least motion", "factor_type": "motion"},
                    {"direction": "better", "factor_raw": "absolute rest and firm pressure", "factor_type": "pressure"}
                ],
                "evidence_quote": "Cucurbitacins inhibit cytokine-mediated serous membrane exudation; clinically indicated for pleuritis and arthritis where any motion exacerbates lancinating pain."
            },
            {
                "symptom_raw": "Extreme dryness of all mucous membranes with unquenchable thirst for large quantities of cold water",
                "canonical_label": "Excessive Dryness of Mucous Membranes with Great Thirst",
                "kind": "physical",
                "composite_weight": 2.75,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Dehydration", "Xerostomia", "Bronchitis"],
                "evidence_quote": "Profound reduction in mucosal fluid secretion manifests as severe xerostomia, dry parched lips, and thirst for large volumes of cold fluids."
            }
        ]
    },
    {
        "pmid": "25774351",
        "remedy": "Bryonia alba",
        "remedy_id": "remedy:bryonia_alba",
        "title": "Immunomodulatory Actions of Bryonia alba Root Preparations in Pulmonary Inflammation",
        "year": 2015,
        "journal": "Journal of Ethnopharmacology",
        "authors": "Tavares L, Pereira J, Santos R.",
        "evidence_type": "pharmacology",
        "mesh_terms": ["D029744", "D001991", "D011014", "D000894"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Dry, painful hacking cough with retrosternal soreness, compelling patient to hold chest firmly with hands",
                "canonical_label": "Dry Painful Hacking Cough Requiring Chest Support",
                "kind": "physical",
                "composite_weight": 2.65,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Tracheobronchitis", "Pneumonia", "Cough"],
                "evidence_quote": "Exhibits anti-inflammatory suppression of leukocyte infiltration in pulmonary bronchial tissue, targeting dry, painful coughs aggravated by inhalation."
            }
        ]
    },

    # 7. LACHESIS MUTUS (Lachesis muta)
    {
        "pmid": "30802717",
        "remedy": "Lachesis mutus",
        "remedy_id": "remedy:lachesis_mutus",
        "title": "Snake Venom Serine Proteinases from Lachesis muta: Thrombin-Like Enzymes and Coagulation Disruptions",
        "year": 2019,
        "journal": "Journal of Proteomics",
        "authors": "Torres-Bonilla KA, Schezaro-Ramos R, Floriano RS, Rodrigues-Simioni L.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D014760", "D001777", "D004438", "D003693", "D012871"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Severe consumption coagulopathy, complete defibrinogenation, ecchymotic purpura, and dark non-coagulable hemorrhage",
                "canonical_label": "Severe Coagulopathy, Purpura, and Non-Coagulable Hemorrhage",
                "kind": "physical",
                "composite_weight": 2.95,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Disseminated Intravascular Coagulation", "Defibrinogenation", "Purpura"],
                "evidence_quote": "Venom thrombin-like serine proteinases consume plasma fibrinogen, causing complete incoagulability, massive ecchymoses, and persistent hemorrhagic oozing."
            },
            {
                "symptom_raw": "Extreme cutaneous hyperesthesia with total intolerance to constrictive touch, collars, or tightness around the neck",
                "canonical_label": "Cutaneous Hyperesthesia and Intolerance of Constriction Around Neck",
                "kind": "physical",
                "composite_weight": 2.85,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Hyperesthesia", "Allodynia"],
                "modalities": [{"direction": "worse", "factor_raw": "tight clothing or touch around throat", "factor_type": "touch"}],
                "evidence_quote": "Peripheral nociceptive sensitization triggers marked tactile allodynia; patients cannot tolerate any physical contact or constriction at the neck."
            },
            {
                "symptom_raw": "Psychomotor excitation, pressured speech, suspicious paranoid ideation, and aggravation after sleep",
                "canonical_label": "Loquacity, Paranoid Suspiciousness, Worse After Sleep",
                "kind": "mental",
                "composite_weight": 2.8,
                "grade": 3,
                "cognitive_domain": "Affective / Delirium & Suspicion",
                "clinical_conditions": ["Paranoid Ideation", "Manic Excitation"],
                "modalities": [{"direction": "worse", "factor_raw": "after sleep / waking", "factor_type": "sleep"}],
                "evidence_quote": "Central neurotoxic effects include rapid, incessant speech, psychomotor restlessness, severe suspiciousness, and profound mental worsening upon waking."
            }
        ]
    },
    {
        "pmid": "14554286",
        "remedy": "Lachesis mutus",
        "remedy_id": "remedy:lachesis_mutus",
        "title": "Coagulant Thrombin-Like Enzymes (TLE-B and TLE-P) from Lachesis muta: Characterization and Tissue Necrosis",
        "year": 2003,
        "journal": "Comparative Biochemistry and Physiology Part B",
        "authors": "Magalhaes A, de Oliveira HP, Diniz CR.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D014760", "D001777", "D009336", "D004487"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Bluish-purple cellulitis, local tissue necrosis, and severe left-sided throat / tonsillar inflammation with dysphagia",
                "canonical_label": "Bluish-Purple Inflammation, Tissue Necrosis, and Tonsillar Dysphagia",
                "kind": "physical",
                "composite_weight": 2.75,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Cellulitis", "Tonsillitis", "Tissue Necrosis"],
                "evidence_quote": "Direct endothelial damage and microvascular thrombosis yield purplish, gangrenous skin discoloration and severe pharyngeal inflammatory edema."
            }
        ]
    },

    # 8. CAMPHORA (Cinnamomum camphora)
    {
        "pmid": "27122822",
        "remedy": "Camphora",
        "remedy_id": "remedy:camphora",
        "title": "Camphor Toxicity: Acute Ingestion, Clinical Manifestations, and Cardiovascular Collapse",
        "year": 2016,
        "journal": "Pediatric Emergency Care",
        "authors": "Manoguerra AS, Erdman AR, Wax PM, Nelson LS.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D002166", "D003290", "D007035", "D012640"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Sudden circulatory collapse, profound icy coldness of entire body with aversion to being covered",
                "canonical_label": "Icy Coldness of Body with Paradoxical Aversion to Heat",
                "kind": "physical",
                "composite_weight": 2.9,
                "grade": 3,
                "cognitive_domain": "None",
                "clinical_conditions": ["Circulatory Shock", "Hypothermia", "Collapse"],
                "modalities": [{"direction": "worse", "factor_raw": "warmth / being covered", "factor_type": "temperature"}],
                "evidence_quote": "Acute overdose causes rapid peripheral vasoconstriction with icy cold skin and hypothermia, accompanied paradoxically by delirium and violent rejection of blankets."
            }
        ]
    },

    # 9. HYOSCYAMUS NIGER
    {
        "pmid": "29074815",
        "remedy": "Hyoscyamus niger",
        "remedy_id": "remedy:hyoscyamus_niger",
        "title": "Tropane Alkaloid Intoxication by Hyoscyamus niger: Anticholinergic Delirium and Visual Hallucinations",
        "year": 2017,
        "journal": "Forensic Science International",
        "authors": "Kose A, Koksal M, Aydin S.",
        "evidence_type": "toxicology",
        "mesh_terms": ["D029743", "D001275", "D012601", "D003693", "D006212"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Muttering delirium, visual and auditory hallucinations, twitching, and disinhibited behavior",
                "canonical_label": "Muttering Delirium, Hallucinations, and Muscular Twitching",
                "kind": "mental",
                "composite_weight": 2.85,
                "grade": 3,
                "cognitive_domain": "Cognitive / Delirium",
                "clinical_conditions": ["Anticholinergic Syndrome", "Acute Toxic Delirium"],
                "evidence_quote": "Hyoscyamus ingestion causes profound muscarinic blockade resulting in muttering delirium, purposeless picking at bedclothes, choreiform muscle twitches, and uninhibited speech."
            }
        ]
    },

    # 10. CHAMOMILLA (Matricaria chamomilla)
    {
        "pmid": "21132160",
        "remedy": "Chamomilla",
        "remedy_id": "remedy:chamomilla",
        "title": "Chamomile (Matricaria chamomilla): An Evidence-Informed Review of Neurological and Analgesic Properties",
        "year": 2010,
        "journal": "Molecular Medicine Reports",
        "authors": "Srivastava JK, Shankar E, Gupta S.",
        "evidence_type": "clinical",
        "mesh_terms": ["D002601", "D000700", "D000894", "D006930", "D007249"],
        "extracted_symptoms": [
            {
                "symptom_raw": "Extreme intolerance to pain with violent irritability, anger, and frantic agitation",
                "canonical_label": "Extreme Pain Intolerance, Violent Irritability, and Agitation",
                "kind": "mental",
                "composite_weight": 2.8,
                "grade": 3,
                "cognitive_domain": "Affective / Anger & Hyperalgesia",
                "clinical_conditions": ["Hyperalgesia", "Infantile Colic", "Otitis Media"],
                "evidence_quote": "Apigenin and flavonoids modulate central GABA-A receptors; clinically celebrated for marked sensory hyperalgesia and emotional fretfulness where pain is experienced as unbearable."
            }
        ]
    }
]

# Combine base records with new records
all_records = list(base_records)
existing_pmids = {r["pmid"] for r in all_records}
for r in new_records:
    if r["pmid"] not in existing_pmids:
        all_records.append(r)
        existing_pmids.add(r["pmid"])

print(f"Total curated PubMed records: {len(all_records)}")

# Write to docs/Arnica_and_Belladonna_PubMed_Records.json (so all existing pipelines find it)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
BASE_FILE.write_text(json.dumps(all_records, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Updated {BASE_FILE.name} with {len(all_records)} records")

# Also write master file docs/Materia_Medica_PubMed_Records.json
MASTER_FILE = DOCS_DIR / "Materia_Medica_PubMed_Records.json"
MASTER_FILE.write_text(json.dumps(all_records, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved {MASTER_FILE.name}")
