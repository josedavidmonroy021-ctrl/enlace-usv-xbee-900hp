# Material suplementario: enlace RF de 900 MHz (XBee-PRO 900HP, FHSS) para un vehículo de superficie no tripulado (USV)

Material suplementario del artículo de proyecto de grado sobre la caracterización de un enlace de comunicaciones de 900 MHz con espectro ensanchado por salto de frecuencia (FHSS) para un USV.

Autores: Juan (Escuela Naval de Cadetes "Almirante Padilla") y CC Guillermo Villalba. Revisor: Dr. Juan Antonio Contreras Montes.

Cómo citar: URL de este repositorio y versión (release) v1.0.

## Contenido

| Carpeta | Contenido |
|---|---|
| `Apendices_completos.pdf` / `.docx` | Los Apéndices A–G completos (material retirado de la versión extensa del artículo, ampliado) |
| `01_tramas_y_variables` | Apéndice A: metodología, variables del sistema y estructura de las tramas de datos; tablas en CSV |
| `02_seleccion_modem_antena_emc` | Apéndice B: selección de módem, antena y compatibilidad electromagnética; capturas de configuración XCTU del radio local; tablas en CSV |
| `03_balance_de_enlace` | Apéndice C: derivación del balance de enlace, atenuación por vegetación y primer elipsoide de Fresnel; tablas en CSV |
| `04_resultados` | Apéndice D (métricas y resultados ampliados) y Apéndice F (contraste con el sistema del Sábalo y discusión ampliada); tablas en CSV |
| `05_espectro` | Apéndice E y capturas originales del analizador de espectro PSA-6000 (potencia de canal en 910 MHz, span 3 MHz; barrido 0–3 GHz de armónicos) |
| `06_datos_crudos` | Datos por ensayo en Excel: escenarios 1–8 (tierra y mar), disponibilidad de 24 h, polarización, recuperación e interferencia |
| `07_codigo` | Scripts de Python de las pruebas (el firmware del STM32F411 se agrega aparte) |
| `08_fotos_de_campo` | Apéndice G y fotografías de las pruebas |
| `09_referencias` | Lista de referencias de los apéndices y copia de los PDF de las fuentes consultadas (`pdf/`). Los derechos de cada documento pertenecen a sus autores o editoriales; se incluyen solo para verificación académica |

Parámetros como ciclos, puerto y horas se ajustaban en cada ensayo; los valores del script son los de su última configuración.

## Licencia

- Código (`07_codigo`): MIT (archivo `LICENSE`).
- Datos, documentos y fotografías: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/deed.es).
