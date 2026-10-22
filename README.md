# Material suplementario: enlace RF de 900 MHz (XBee-PRO 900HP, FHSS) para un vehículo de superficie no tripulado (USV)

Material suplementario del artículo de proyecto de grado sobre la caracterización de un enlace de comunicaciones de 900 MHz con espectro ensanchado por salto de frecuencia (FHSS) para un USV.

Autores: Juan (Escuela Naval de Cadetes "Almirante Padilla") y CC Guillermo Villalba. Revisor: Dr. Juan Antonio Contreras Montes.

Cómo citar: URL de este repositorio y versión (release) v1.1.

## Contenido

| Carpeta | Contenido |
|---|---|
| `Apendices_completos.pdf` / `.docx` | Los Apéndices A–T completos, en el orden en que se citan en el artículo |
| `Apendices/` | Un PDF por apéndice (A–T), al que enlaza cada llamada del artículo |
| `01_tramas_y_variables` | Tablas en CSV de los Apéndices A y B |
| `02_seleccion_modem_antena_emc` | Tablas en CSV de los Apéndices D, E y F; capturas de configuración XCTU del radio local |
| `03_balance_de_enlace` | Tablas en CSV de los Apéndices C y J |
| `04_resultados` | Tablas en CSV de los Apéndices K y Q |
| `05_espectro` | Capturas originales del analizador de espectro PSA-6000 (Apéndices N y O): potencia de canal en 910 MHz, span 3 MHz; barrido 0–3 GHz de armónicos |
| `06_datos_crudos` | Datos por ensayo en Excel: escenarios 1–8 (tierra y mar), disponibilidad de 24 h, polarización, recuperación e interferencia |
| `07_codigo` | Código fuente (Apéndice G): `python/` (scripts de las pruebas de la estación base) y `Xbee_bidireccional_at_v2/` (firmware del STM32F411) |
| `08_fotos_de_campo` | Fotografías de las pruebas (Apéndice I) |
| `09_referencias` | Lista de referencias de los apéndices y copia de los PDF de las fuentes consultadas (`pdf/`). Los derechos de cada documento pertenecen a sus autores o editoriales; se incluyen solo para verificación académica |

### Apéndices

| Apéndice | Contenido |
|---|---|
| A | Metodología de diseño electrónico, variables del sistema y arquitectura del enlace |
| B | Estructura de las tramas de datos |
| C | Modelos de propagación y atenuación adicional en el balance de enlace |
| D | Selección del módem |
| E | Selección de antenas |
| F | Estudio de compatibilidad electromagnética (EMC) |
| G | Código fuente del banco de pruebas (Python y Visual Studio Code) |
| H | Programación del protocolo y banco de pruebas |
| I | Registro fotográfico de las pruebas |
| J | Márgenes teóricos y límites operativos en campo |
| K | Consolidado de métricas de rendimiento y calidad de servicio por escenario |
| L | Prueba de recuperación del enlace |
| M | Polarización de la antena y disponibilidad continua |
| N | Registros del analizador de espectro: potencia de canal por nivel de potencia |
| O | Pureza espectral: barrido de banda ancha y armónicos |
| P | Prueba de interferencia: espectro del analizador de XCTU |
| Q | Contraste con el Sábalo, interpretación de los hallazgos y síntesis de resultados |
| R | Dinámica de propagación y contraste entre el modelo teórico y las mediciones |
| S | Antenas, recuperación del enlace y orientación de las antenas |
| T | Pureza espectral, interferencia y máscara de canales (discusión ampliada) |

Parámetros como ciclos, puerto y horas se ajustaban en cada ensayo; los valores del script son los de su última configuración.

## Licencia

- Código (`07_codigo`): MIT (archivo `LICENSE`).
- Datos, documentos y fotografías: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/deed.es).
