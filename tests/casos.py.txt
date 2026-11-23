"""Casos de prueba compartidos (funcionales, extremos e inválidos).
Estructura de cada caso: (id, tipo, descripcion, payload, status_esperado, nivel_esperado)
(
    "F02",                          # 1. ID único de la prueba
    "funcional",                    # 2. Tipo de categoría (funcional, extremo, inválido)
    "Cliente en riesgo...",         # 3. Descripción legible de lo que prueba el caso
    { ... },                        # 4. El Payload (diccionario con los datos del cliente que se envían a la API)
    200,                            # 5. Status HTTP esperado (200 = Éxito)
    "Alto"                          # 6. Nivel de riesgo esperado que debe devolver el modelo
)
"""


CASOS = [
    # -------------------------------------------------------------------------
    # CASO BASE (REFERENCIA)
    # -------------------------------------------------------------------------
    (
        "BAS", 
        "base", 
        "Perfil base estándar de referencia",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 24, 
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 55.0, 
            "TotalCharges": 1320.0,
        }, 
        200, 
        None
    ),

    # -------------------------------------------------------------------------
    # CASOS FUNCIONALES
    # -------------------------------------------------------------------------
    (
        "F01", 
        "funcional", 
        "Cliente fiel: contrato 2 años, 72 meses, DSL",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 72,                          # CAMBIO: 72 meses (vs 24 base)
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "Two year",                # CAMBIO: Dos años (vs One year base)
            "PaperlessBilling": "No", 
            "PaymentMethod": "Credit card (automatic)", # CAMBIO: Tarjeta de crédito (vs Mailed check base)
            "MonthlyCharges": 64.5,                # CAMBIO: 64.5 (vs 55.0 base)
            "TotalCharges": 4644.0,                # CAMBIO: 4644.0 (vs 1320.0 base)
        }, 
        200, 
        "Bajo"
    ),
    (
        "F02", 
        "funcional", 
        "Cliente en riesgo (real, conjunto de prueba 9611-CTWIH, churn=1)",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "No",                       # CAMBIO: No tiene pareja (vs Yes base)
            "Dependents": "No",
            "tenure": 3,                           # CAMBIO: 3 meses (vs 24 base)
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "Fiber optic",      # CAMBIO: Fibra óptica (vs DSL base)
            "OnlineSecurity": "No",                # CAMBIO: Sin seguridad (vs Yes base)
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "No",                   # CAMBIO: Sin soporte técnico (vs Yes base)
            "StreamingTV": "Yes",                  # CAMBIO: Con TV (vs No base)
            "StreamingMovies": "Yes",              # CAMBIO: Con películas (vs No base)
            "Contract": "Month-to-month",          # CAMBIO: Mes a mes (vs One year base)
            "PaperlessBilling": "Yes",             # CAMBIO: Facturación electrónica (vs No base)
            "PaymentMethod": "Electronic check",   # CAMBIO: Cheque electrónico (vs Mailed check base)
            "MonthlyCharges": 89.45,               # CAMBIO: 89.45 (vs 55.0 base)
            "TotalCharges": 240.45,                # CAMBIO: 240.45 (vs 1320.0 base)
        }, 
        200, 
        "Alto"
    ),
    (
        "F03", 
        "funcional", 
        "Cliente intermedio: contrato 1 año, 24 meses (Perfil Base estándar)",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 24, 
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 55.0, 
            "TotalCharges": 1320.0,
        }, 
        200, 
        None
    ),

    # -------------------------------------------------------------------------
    # CASOS EXTREMOS
    # -------------------------------------------------------------------------
    (
        "E01", 
        "extremo", 
        "Cliente nuevo: tenure=0 y TotalCharges=0",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 0,                           # CAMBIO: 0 meses (vs 24 base)
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "Month-to-month",          # CAMBIO: Mes a mes (vs One year base)
            "PaperlessBilling": "No", 
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 55.0, 
            "TotalCharges": 0.0,                   # CAMBIO: 0.0 (vs 1320.0 base)
        }, 
        200, 
        None
    ),
    (
        "E02", 
        "extremo", 
        "Límite superior de datos: tenure=72, cargos máximos",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 72,                          # CAMBIO: 72 meses (vs 24 base)
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "Two year",                # CAMBIO: Dos años (vs One year base)
            "PaperlessBilling": "No", 
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 118.75,              # CAMBIO: 118.75 (vs 55.0 base)
            "TotalCharges": 8684.8,                # CAMBIO: 8684.8 (vs 1320.0 base)
        }, 
        200, 
        None
    ),
    (
        "E03", 
        "extremo", 
        "Cargo mensual mínimo (18.25) sin internet",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 24, 
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "No",               # CAMBIO: Sin internet (vs DSL base)
            "OnlineSecurity": "No",                # CAMBIO: Desactivado (vs Yes base)
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "No",                   # CAMBIO: Desactivado (vs Yes base)
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 18.25,               # CAMBIO: 18.25 (vs 55.0 base)
            "TotalCharges": 438.0,                 # CAMBIO: 438.0 (vs 1320.0 base)
        }, 
        200, 
        None
    ),
    (
        "E04", 
        "extremo", 
        "Peor perfil posible: mes a mes, fibra, cheque electrónico, 1 mes",
        {
            "gender": "Female", 
            "SeniorCitizen": "Yes",                # CAMBIO: Es adulto mayor (vs No base)
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 1,                           # CAMBIO: 1 mes (vs 24 base)
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "Fiber optic",      # CAMBIO: Fibra óptica (vs DSL base)
            "OnlineSecurity": "No",                # CAMBIO: Sin seguridad (vs Yes base)
            "OnlineBackup": "No",                  # CAMBIO: Sin respaldo (vs No base)
            "DeviceProtection": "No", 
            "TechSupport": "No",                   # CAMBIO: Sin soporte (vs Yes base)
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "Month-to-month",          # CAMBIO: Mes a mes (vs One year base)
            "PaperlessBilling": "No", 
            "PaymentMethod": "Electronic check",   # CAMBIO: Cheque electrónico (vs Mailed check base)
            "MonthlyCharges": 95.0,                # CAMBIO: 95.0 (vs 55.0 base)
            "TotalCharges": 95.0,                  # CAMBIO: 95.0 (vs 1320.0 base)
        }, 
        200, 
        "Medio"
    ),
    (
        "E05", 
        "extremo", 
        "Inconsistente: tenure=0 pero TotalCharges=5000",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 0,                           # CAMBIO: 0 meses (vs 24 base)
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 55.0, 
            "TotalCharges": 5000.0,                # CAMBIO: 5000.0 (vs 1320.0 base)
        }, 
        200, 
        None
    ),

    # -------------------------------------------------------------------------
    # CASOS INVÁLIDOS
    # -------------------------------------------------------------------------
    (
        "I01", 
        "inválido", 
        "tenure negativo",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": -5,                          # CAMBIO: Negativo (vs 24 base)
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 55.0, 
            "TotalCharges": 1320.0,
        }, 
        422, 
        None
    ),
    (
        "I02", 
        "inválido", 
        "Categoría inexistente en Contract",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 24, 
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "Three year",              # CAMBIO: Inválido (vs One year base)
            "PaperlessBilling": "No", 
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 55.0, 
            "TotalCharges": 1320.0,
        }, 
        422, 
        None
    ),
    (
        "I03", 
        "inválido", 
        "Campo faltante (sin MonthlyCharges)",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 24, 
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            # "MonthlyCharges": 55.0,              # CAMBIO: Campo eliminado
            "TotalCharges": 1320.0,
        }, 
        422, 
        None
    ),
    (
        "I04", 
        "inválido", 
        "Texto en campo numérico",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 24, 
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": "abc",               # CAMBIO: Texto en vez de número (vs 55.0 base)
            "TotalCharges": 1320.0,
        }, 
        422, 
        None
    ),
    (
        "I05", 
        "inválido", 
        "TotalCharges absurdo (1e9)",
        {
            "gender": "Female", 
            "SeniorCitizen": "No", 
            "Partner": "Yes", 
            "Dependents": "No",
            "tenure": 24, 
            "PhoneService": "Yes", 
            "MultipleLines": "No", 
            "InternetService": "DSL",
            "OnlineSecurity": "Yes", 
            "OnlineBackup": "No", 
            "DeviceProtection": "No", 
            "TechSupport": "Yes",
            "StreamingTV": "No", 
            "StreamingMovies": "No", 
            "Contract": "One year", 
            "PaperlessBilling": "No",
            "PaymentMethod": "Mailed check", 
            "MonthlyCharges": 55.0, 
            "TotalCharges": 1e9,                   # CAMBIO: Valor absurdo (vs 1320.0 base)
        }, 
        422, 
        None
    ),
    (
        "I06", 
        "inválido", 
        "Cuerpo vacío",
        {},                                        # CAMBIO: Diccionario vacío
        422, 
        None
    ),
]