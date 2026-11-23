# Runbook RB-01 · Data drift y degradación de calidad del modelo de churn

## 1. Señal que activa el runbook
- Métrica (monitor.py, ventana de 500 solicitudes): `drift_psi` (PSI máximo entre `tenure`, `MonthlyCharges`, `TotalCharges`, `Contract`, `InternetService`, `PaymentMethod`), `contact_rate_shift_pts`, `mean_prob_shift` y, cuando llegan etiquetas, `recall`.
- Umbral: `drift_psi` ≥ 0.25 (critical) o ≥ 0.10 (warning, solo alerta si persiste 2 ventanas); `contact_rate_shift_pts` ≥ 20; `mean_prob_shift` ≥ 0.10; `recall` ≤ 0.70.
- Severidad: **P2** (drift y comportamiento) · **P1** si `recall` ≤ 0.70.
- Las alertas de esta familia se agrupan en **un solo incidente** porque comparten causa y respuesta.

## 2. Impacto esperado
El modelo recibe clientes con un perfil que no vio al entrenarse, así que sus probabilidades son menos confiables. En la práctica: (a) se marcan muchos más clientes "contactar" que el presupuesto de campaña previsto (51% de referencia), y cada contacto cuesta $46 MXN; o (b) si el recall cae, se dejan ir clientes que se podían retener (beneficio esperado de $244.80 por cliente retenido).

## 3. Diagnóstico inicial
1. **Descartar un fallo de ingesta:** en `monitoring_summary.json` revisar que `invalid_request_rate` y `error_rate` estén en ≈ 0 (los datos llegan completos y válidos).
2. **Localizar la causa:** en el dashboard (panel «PSI por variable») ver qué variables se movieron. Varias variables coherentes entre sí (mes a mes + fibra óptica + poca antigüedad) indican un cambio real de población, no un error de una columna.
3. **Buscar la explicación de negocio:** ¿hay campaña de captación, promoción o cambio de planes en estas fechas? Confirmarlo con el responsable comercial.
4. **Cuantificar el costo:** contactos extra = (contact_rate − 0.508) × clientes; costo extra = contactos extra × $46.
5. **Medir calidad si ya hay etiquetas:** `python monitoring\src\monitor.py --window-label <ventana>_con_etiquetas --labels monitoring\data\labels_delayed.csv` y comparar `recall`/`precision`/`f1` con la referencia (0.874 / 0.457 / 0.60).

## 4. Acción principal
Automática, con `python monitoring\src\respond.py --execute`:
- **Cuarentena del lote:** la ventana no dispara la campaña completa; se limita al **presupuesto de campaña** (top X% por probabilidad, X = 50.8%). Los demás clientes quedan **en espera**, no se descartan (`outputs/quarantine/`).
- **Solicitud de reentrenamiento** (`outputs/retraining_request.json`), máximo una abierta. **Nunca se despliega un modelo nuevo sin aprobación humana.**

Decisión humana al llegar las etiquetas:
| Resultado con etiquetas | Decisión |
|---|---|
| recall ≥ 0.80 y precision no cae más de 10 pts | El modelo sigue válido: liberar la cola en espera y mantener el reentrenamiento como mejora |
| recall < 0.80 o precision cae más de 10 pts | Mantener el tope, entrenar un modelo challenger con la población nueva y compararlo (prueba A/B como en la Actividad 6) antes de aprobar |

## 5. Validación de recuperación
- `drift_psi` < 0.10 en **2 ventanas consecutivas** con tráfico habitual (o, si el cambio es permanente, < 0.10 contra el nuevo baseline tras reentrenar).
- `contact_rate_shift_pts` < 10 y `mean_prob_shift` < 0.05.
- Cuarentena liberada o cerrada, y solicitud de reentrenamiento resuelta o programada.

## 6. Evidencia a conservar
Dashboard con la ventana del incidente · `alerts.json` y `monitoring_summary.json` · `response_log.jsonl` · `quarantine/*_lista_contacto.csv` · `retraining_request.json` · corridas de MLflow (monitor y respond) · dashboard posterior con las ventanas recuperadas.

## 7. Mejora posterior
Reentrenamiento programado con datos recientes; PSI por segmento de captación; avisar al área comercial antes de lanzar campañas para anticipar el cambio de perfil; conectar la solicitud de reentrenamiento al pipeline de la Fase III (CI/CD con aprobación manual).
