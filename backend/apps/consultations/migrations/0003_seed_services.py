# Seed du référentiel des 47 services d'orientation (section « ➡️ Orientation »
# de l'étape « Admission & Pré-consultation » du prototype) — voir
# `orientServices` dans MediRophe_FicheConsultation...html (~ligne 16208).

from django.db import migrations

SERVICES = [
    ("clinique", "Médecine interne / Générale", "Prise en charge globale des pathologies médicales (diabète, hypertension, infections)."),
    ("clinique", "Chirurgie", "Interventions chirurgicales programmées ou en urgence (générale, orthopédique, digestive, etc.)."),
    ("clinique", "Pédiatrie", "Soins des enfants de 0 à 15 ans (consultations, hospitalisation, suivi)."),
    ("clinique", "Gynécologie-Obstétrique", "Suivi de la grossesse, accouchement, pathologies gynécologiques (cancer du col, endométriose)."),
    ("clinique", "Cardiologie", "Prise en charge des maladies du cœur et des vaisseaux (infarctus, insuffisance cardiaque, HTA)."),
    ("clinique", "Neurologie", "Prise en charge des pathologies du système nerveux (AVC, épilepsie, Parkinson, Alzheimer)."),
    ("clinique", "Pneumologie", "Pathologies respiratoires (asthme, BPCO, tuberculose, infections pulmonaires)."),
    ("clinique", "Gastro-entérologie", "Pathologies digestives et hépatiques (hépatite, cirrhose, ulcère, cancer digestif)."),
    ("clinique", "Néphrologie", "Pathologies rénales (insuffisance rénale, dialyse, transplantation rénale)."),
    ("clinique", "Endocrinologie", "Pathologies hormonales (diabète, thyroïde, obésité)."),
    ("clinique", "Rhumatologie", "Pathologies ostéo-articulaires (arthrose, polyarthrite, ostéoporose, lombalgies)."),
    ("clinique", "Dermatologie", "Pathologies de la peau (eczéma, psoriasis, infections cutanées, mélanome)."),
    ("clinique", "Ophtalmologie", "Pathologies de l'œil (cataracte, glaucome, DMLA, troubles de la vision)."),
    ("clinique", "ORL", "Pathologies de l'oreille, du nez et de la gorge (sinusite, otite, amygdalite, perte d'audition)."),
    ("clinique", "Psychiatrie", "Prise en charge des troubles mentaux (dépression, schizophrénie, anxiété, addictions)."),
    ("clinique", "Pédopsychiatrie", "Prise en charge des troubles mentaux chez l'enfant et l'adolescent."),
    ("clinique", "Gériatrie", "Soins des personnes âgées, prévention des chutes, maladies chroniques, Alzheimer."),
    ("clinique", "Oncologie", "Prise en charge des cancers (chimiothérapie, radiothérapie, suivi post-traitement)."),
    ("clinique", "Hématologie", "Pathologies du sang (leucémies, lymphomes, anémies, troubles de la coagulation)."),
    ("clinique", "Infectiologie", "Prise en charge des maladies infectieuses (VIH, hépatites, paludisme, tuberculose)."),
    ("clinique", "Urgences (SAU)", "Accueil et prise en charge immédiate des situations critiques (traumatismes, AVC, infarctus)."),
    ("clinique", "Réanimation / Soins intensifs", "Prise en charge des patients en état critique nécessitant une surveillance continue."),
    ("clinique", "Médecine du travail", "Suivi médical des salariés, prévention des risques professionnels."),
    ("clinique", "Médecine sportive", "Suivi des sportifs, bilan pré-compétition, rééducation après blessure."),
    ("clinique", "Médecine palliative", "Accompagnement des patients en fin de vie, contrôle de la douleur."),
    ("fonctionnel", "Biologie médicale (Laboratoire)", "Analyses biologiques (prises de sang, ECBU, prélèvements, sérologies, hématologie, biochimie)."),
    ("fonctionnel", "Imagerie médicale (Radiologie)", "Examens d'imagerie (radiographie, échographie, scanner, IRM, mammographie)."),
    ("fonctionnel", "Anatomopathologie", "Analyse de tissus et cellules (biopsies, frottis cervico-utérin, histologie)."),
    ("fonctionnel", "Pharmacie", "Gestion et délivrance des médicaments, préparation des chimiothérapies, conseil médicamenteux."),
    ("fonctionnel", "Explorations fonctionnelles", "Examens fonctionnels (ECG, épreuve d'effort, explorations vasculaires, spirométrie)."),
    ("fonctionnel", "Rééducation & Réadaptation (Kinésithérapie)", "Kinésithérapie, orthophonie, ergothérapie."),
    ("fonctionnel", "Dialyse", "Prise en charge des patients en insuffisance rénale terminale."),
    ("fonctionnel", "Don de sang / Transfusion", "Collecte et délivrance des produits sanguins."),
    ("fonctionnel", "Cryopréservation / Biobanque", "Conservation d'échantillons biologiques pour la recherche."),
    ("support", "Accueil / Admissions", "Accueil des patients, création des dossiers administratifs, orientation."),
    ("support", "Secrétariat médical", "Gestion des rendez-vous, des dossiers médicaux, de la correspondance."),
    ("support", "Archives médicales", "Conservation et gestion des dossiers patients."),
    ("support", "Système d'information (SI)", "Gestion des données, interopérabilité, sécurité des systèmes."),
    ("support", "Gestion des lits", "Gestion des capacités d'hospitalisation."),
    ("support", "Bloc opératoire", "Salles d'opération et équipes dédiées."),
    ("support", "Stérilisation", "Nettoyage et stérilisation du matériel médical."),
    ("transversal", "Hôpital de jour", "Hospitalisation de courte durée pour examens, chimiothérapie, soins techniques."),
    ("transversal", "Consultations externes", "Consultations programmées sans hospitalisation."),
    ("transversal", "Soins à domicile (HAD)", "Soins délivrés au domicile du patient."),
    ("transversal", "Télémédecine", "Consultations à distance (téléconsultation, télésuivi, téléexpertise)."),
    ("transversal", "Éducation thérapeutique", "Accompagnement des patients dans la gestion de leur maladie chronique."),
    ("transversal", "Médecine préventive", "Dépistage, vaccination, bilans de santé."),
]


def seed_services(apps, schema_editor):
    Service = apps.get_model("consultations", "Service")
    Service.objects.bulk_create(
        [Service(categorie=categorie, nom=nom, role_principal=role) for categorie, nom, role in SERVICES]
    )


def unseed_services(apps, schema_editor):
    Service = apps.get_model("consultations", "Service")
    Service.objects.filter(nom__in=[nom for _categorie, nom, _role in SERVICES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("consultations", "0002_service_consultation_medecin_oriente_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_services, unseed_services),
    ]
