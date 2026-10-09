# Seed du référentiel des 103 examens de laboratoire — voir `examTable` dans
# MediRophe_FicheConsultation...html (~ligne 22452). `prix_fcfa` est le
# montant numérique extrait de la chaîne `price` du prototype (ex. "3 000
# FCFA" -> 3000), même logique que `parsePrice()` côté prototype.

from django.db import migrations

# (code, nom, categorie, unite, taux_cmu, prix_fcfa, duree_estimee, actif)
EXAMENS = [
    ("MET-01", "Glycémie à jeun", "metabolisme", "g/L", 80, 3000, "2h", True),
    ("MET-02", "Glycémie post-prandiale", "metabolisme", "g/L", 80, 3000, "2h", True),
    ("MET-03", "HbA1c", "metabolisme", "%", 80, 6000, "3h", True),
    ("MET-04", "Cholestérol total", "metabolisme", "g/L", 80, 4500, "3h", True),
    ("MET-05", "HDL Cholestérol", "metabolisme", "g/L", 80, 4000, "3h", True),
    ("MET-06", "LDL Cholestérol", "metabolisme", "g/L", 80, 4000, "3h", True),
    ("MET-07", "Triglycérides", "metabolisme", "g/L", 80, 4000, "3h", True),
    ("MET-08", "Acide urique", "metabolisme", "mg/L", 80, 3500, "2h", True),
    ("REN-01", "Créatinine", "renal", "mg/L", 80, 3500, "2h", True),
    ("REN-02", "Urée", "renal", "g/L", 80, 3000, "2h", True),
    ("REN-03", "Clairance de la créatinine", "renal", "mL/min", 80, 5000, "4h", True),
    ("REN-04", "Ionogramme sanguin (Na/K/Cl)", "renal", "mmol/L", 80, 5500, "3h", True),
    ("REN-05", "Microalbuminurie", "renal", "mg/24h", 80, 6000, "6h", True),
    ("REN-06", "Cystatine C", "renal", "mg/L", 80, 9000, "24h", True),
    ("HEP-01", "ASAT", "hepatique", "UI/L", 70, 4000, "3h", True),
    ("HEP-02", "ALAT", "hepatique", "UI/L", 70, 4000, "3h", True),
    ("HEP-03", "Gamma GT", "hepatique", "UI/L", 70, 4000, "3h", True),
    ("HEP-04", "Phosphatases alcalines", "hepatique", "UI/L", 70, 4000, "3h", True),
    ("HEP-05", "Bilirubine totale", "hepatique", "mg/L", 70, 3500, "3h", True),
    ("HEP-06", "Bilirubine directe", "hepatique", "mg/L", 70, 3500, "3h", True),
    ("HEP-07", "Albumine", "hepatique", "g/L", 70, 4000, "3h", True),
    ("HEP-08", "Taux de prothrombine (TP)", "hepatique", "%", 70, 4500, "3h", True),
    ("INF-01", "CRP", "inflammation", "mg/L", 70, 5000, "4h", True),
    ("INF-02", "CRP ultrasensible", "inflammation", "mg/L", 70, 6500, "4h", True),
    ("INF-03", "Vitesse de sédimentation (VS)", "inflammation", "mm/1h", 70, 3000, "2h", True),
    ("INF-04", "Fibrinogène", "inflammation", "g/L", 70, 4500, "3h", True),
    ("HEM-01", "NFS complète", "hematologie", "—", 80, 7000, "2h", True),
    ("HEM-02", "Hémoglobine", "hematologie", "g/dL", 80, 3000, "1h", True),
    ("HEM-03", "Hématocrite", "hematologie", "%", 80, 3000, "1h", True),
    ("HEM-04", "Numération plaquettaire", "hematologie", "G/L", 80, 3500, "2h", True),
    ("HEM-05", "Groupe sanguin ABO/Rhésus", "hematologie", "—", 80, 4000, "2h", True),
    ("HEM-06", "Réticulocytes", "hematologie", "G/L", 80, 4500, "3h", True),
    ("HEM-07", "Ferritine", "hematologie", "ng/mL", 80, 6500, "4h", True),
    ("HEM-08", "Fer sérique", "hematologie", "µg/dL", 80, 4000, "3h", True),
    ("HEM-09", "Transferrine", "hematologie", "g/L", 80, 5000, "3h", True),
    ("END-01", "TSH", "endocrinologie", "mUI/L", 60, 8000, "24h", True),
    ("END-02", "T3 libre", "endocrinologie", "pg/mL", 60, 7000, "24h", True),
    ("END-03", "T4 libre", "endocrinologie", "ng/dL", 60, 7000, "24h", True),
    ("END-04", "Cortisol", "endocrinologie", "µg/dL", 60, 9000, "24h", True),
    ("END-05", "Insuline à jeun", "endocrinologie", "µUI/mL", 60, 8500, "24h", True),
    ("END-06", "Parathormone (PTH)", "endocrinologie", "pg/mL", 60, 12000, "48h", True),
    ("END-07", "Testostérone totale", "endocrinologie", "ng/dL", 60, 9500, "24h", True),
    ("END-08", "Prolactine", "endocrinologie", "ng/mL", 60, 8000, "24h", True),
    ("CAR-01", "Troponine I", "cardiologie", "ng/L", 70, 12000, "1h", True),
    ("CAR-02", "CK-MB", "cardiologie", "UI/L", 70, 7000, "3h", True),
    ("CAR-03", "BNP (NT-proBNP)", "cardiologie", "pg/mL", 70, 15000, "4h", True),
    ("CAR-04", "CPK totale", "cardiologie", "UI/L", 70, 5000, "3h", True),
    ("CAR-05", "LDH", "cardiologie", "UI/L", 70, 4500, "3h", True),
    ("VIT-01", "Vitamine D (25-OH)", "vitamines_mineraux", "ng/mL", 30, 10000, "24h", True),
    ("VIT-02", "Vitamine B12", "vitamines_mineraux", "pg/mL", 30, 8500, "24h", True),
    ("VIT-03", "Folates (Vitamine B9)", "vitamines_mineraux", "ng/mL", 30, 8000, "24h", True),
    ("VIT-04", "Magnésium", "vitamines_mineraux", "mg/L", 30, 3500, "2h", True),
    ("VIT-05", "Calcium sérique", "vitamines_mineraux", "mg/L", 30, 3500, "2h", True),
    ("VIT-06", "Phosphore", "vitamines_mineraux", "mg/L", 30, 3500, "2h", True),
    ("INS-01", "VIH (sérologie)", "infectiologie_serologie", "—", 60, 8000, "24h", True),
    ("INS-02", "Hépatite B (Ag HBs)", "infectiologie_serologie", "—", 60, 7000, "24h", True),
    ("INS-03", "Hépatite C (Ac anti-VHC)", "infectiologie_serologie", "—", 60, 7000, "24h", True),
    ("INS-04", "Syphilis (TPHA-VDRL)", "infectiologie_serologie", "—", 60, 6000, "24h", True),
    ("INS-05", "Toxoplasmose (IgG/IgM)", "infectiologie_serologie", "—", 60, 7500, "24h", True),
    ("INS-06", "Rubéole (IgG/IgM)", "infectiologie_serologie", "—", 60, 7500, "24h", True),
    ("INS-07", "CMV (IgG/IgM)", "infectiologie_serologie", "—", 60, 8000, "24h", True),
    ("INS-08", "Widal-Félix (typhoïde)", "infectiologie_serologie", "—", 60, 5000, "24h", False),
    ("INS-09", "Goutte épaisse (paludisme)", "infectiologie_serologie", "—", 60, 3000, "1h", True),
    ("INS-10", "Test rapide paludisme (TDR)", "infectiologie_serologie", "—", 60, 2500, "30min", True),
    ("INS-11", "ECBU (cytobactériologie urinaire)", "infectiologie_serologie", "—", 60, 6000, "48h", True),
    ("GYN-01", "Frottis cervico-vaginal (FCU)", "gynecologie_cytologie", "—", 60, 10000, "72h", True),
    ("GYN-02", "Test HPV HR (génotypage 16/18/45)", "gynecologie_cytologie", "—", 60, 15000, "72h", True),
    ("GYN-03", "Colposcopie", "gynecologie_cytologie", "—", 60, 12000, "24h", True),
    ("GYN-04", "Biopsie / Anatomopathologie (col utérin)", "gynecologie_cytologie", "—", 60, 20000, "5j", True),
    ("COA-01", "TP / INR", "coagulation", "%", 70, 4500, "3h", True),
    ("COA-02", "TCA", "coagulation", "sec", 70, 4000, "3h", True),
    ("COA-03", "D-Dimères", "coagulation", "µg/L", 70, 9000, "4h", True),
    ("COA-04", "Temps de saignement", "coagulation", "min", 70, 3000, "2h", True),
    ("TUM-01", "PSA total", "marqueurs_tumoraux", "ng/mL", 50, 9000, "24h", True),
    ("TUM-02", "CA 125", "marqueurs_tumoraux", "U/mL", 50, 11000, "24h", True),
    ("TUM-03", "CA 19-9", "marqueurs_tumoraux", "U/mL", 50, 11000, "24h", True),
    ("TUM-04", "CA 15-3", "marqueurs_tumoraux", "U/mL", 50, 11000, "24h", True),
    ("TUM-05", "ACE", "marqueurs_tumoraux", "ng/mL", 50, 10000, "24h", True),
    ("TUM-06", "AFP", "marqueurs_tumoraux", "ng/mL", 50, 10000, "24h", True),
    ("TUM-07", "PSA libre/total", "marqueurs_tumoraux", "ratio", 50, 12000, "24h", True),
    ("HOR-01", "Beta-hCG quantitatif", "hormonal_fertilite", "mUI/mL", 40, 8000, "3h", True),
    ("HOR-02", "FSH", "hormonal_fertilite", "UI/L", 40, 8000, "24h", True),
    ("HOR-03", "LH", "hormonal_fertilite", "UI/L", 40, 8000, "24h", True),
    ("HOR-04", "Œstradiol", "hormonal_fertilite", "pg/mL", 40, 9000, "24h", True),
    ("HOR-05", "Progestérone", "hormonal_fertilite", "ng/mL", 40, 9000, "24h", True),
    ("HOR-06", "AMH (réserve ovarienne)", "hormonal_fertilite", "ng/mL", 40, 15000, "48h", True),
    ("IMA-01", "Facteur rhumatoïde", "immunologie_allergie", "UI/mL", 50, 6000, "24h", True),
    ("IMA-02", "Anticorps anti-CCP", "immunologie_allergie", "U/mL", 50, 12000, "48h", True),
    ("IMA-03", "ANA (anticorps antinucléaires)", "immunologie_allergie", "—", 50, 10000, "48h", True),
    ("IMA-04", "IgE totales", "immunologie_allergie", "UI/mL", 50, 6500, "24h", True),
    ("IMA-05", "Bilan allergénique (Phadiatop)", "immunologie_allergie", "—", 50, 15000, "48h", True),
    ("PAR-01", "Examen parasitologique des selles (EPS)", "parasitologie_microbiologie", "—", 70, 4000, "24h", True),
    ("PAR-02", "Sérologie amibiase", "parasitologie_microbiologie", "—", 70, 6000, "24h", True),
    ("PAR-03", "Prélèvement vaginal (PV)", "parasitologie_microbiologie", "—", 70, 6500, "48h", True),
    ("PAR-04", "Spermogramme", "parasitologie_microbiologie", "—", 70, 8000, "24h", True),
    ("PAR-05", "Antibiogramme", "parasitologie_microbiologie", "—", 70, 5000, "48h", True),
    ("TOX-01", "Alcoolémie", "toxicologie", "g/L", 0, 4000, "1h", True),
    ("TOX-02", "Recherche de stupéfiants (urinaire)", "toxicologie", "—", 0, 8000, "3h", True),
    ("TOX-03", "Plombémie", "toxicologie", "µg/dL", 0, 9500, "48h", True),
    ("TOX-04", "Carboxyhémoglobine", "toxicologie", "%", 0, 5000, "1h", True),
    ("GRO-01", "Bilan prénatal complet", "bilan_prenatal_grossesse", "—", 90, 20000, "48h", True),
    ("GRO-02", "Sérologie toxoplasmose grossesse", "bilan_prenatal_grossesse", "—", 90, 7500, "24h", True),
    ("GRO-03", "Groupe sanguin + RAI", "bilan_prenatal_grossesse", "—", 90, 5500, "24h", True),
]


def seed_examens(apps, schema_editor):
    Examen = apps.get_model("prescriptions", "Examen")
    Examen.objects.bulk_create(
        [
            Examen(
                code=code,
                nom=nom,
                categorie=categorie,
                unite=unite,
                taux_cmu=taux_cmu,
                prix_fcfa=prix_fcfa,
                duree_estimee=duree_estimee,
                actif=actif,
            )
            for code, nom, categorie, unite, taux_cmu, prix_fcfa, duree_estimee, actif in EXAMENS
        ]
    )


def unseed_examens(apps, schema_editor):
    Examen = apps.get_model("prescriptions", "Examen")
    Examen.objects.filter(code__in=[code for code, *_rest in EXAMENS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("prescriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_examens, unseed_examens),
    ]
