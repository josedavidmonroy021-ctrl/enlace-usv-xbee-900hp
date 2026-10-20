import serial
import time
import statistics
import os
import pandas as pd
import numpy as np

# ==============================================================================
# CONFIGURACIÓN DE PARÁMETROS DE LA PRUEBA DE RECUPERACIÓN DE ENLACE
# ==============================================================================
PORT = 'COM4'                   # Puerto Serie en Estación de Tierra
BAUD_RATE = 115200             # Baudrate
TOTAL_PACKETS = 500            # Cantidad total de ciclos
SAMPLE_RSSI_EVERY = 0          # Desactivado (0) para no congelar el canal en pruebas de recuperación
TIMEOUT_SEC = 0.8            # Tiempo máximo de espera por $PUSVD (segundos)
INTERVAL_SEC = 0.4            # Intervalo entre transmisiones de control (segundos)

# MACs del Enlace
MAC_BASE = "0013A200419110BB"
MAC_USV = "0013A20041867349"

# TRAMA DE SALIDA (Estación de Tierra -> USV)
TRAMA_CONTROL_TEXT = "$PUSVU,1500.0,1500.0,+00,01*42\r\n"
TX_BYTES = TRAMA_CONTROL_TEXT.encode('utf-8')

# TRAMA DE ENTRADA ESPERADA (USV -> Estación de Tierra)
TRAMA_TELEMETRIA_TEXT = "$PUSVD,102831.00,1024.7404,N,07531.9268,W,1,08,1.2,5.0,M,12.5,N,185.4,T,185.0,T,+1.2,P,-0.5,R,24.5,C,1,12.4,V,2.3,C,1,STATE,1*4F\r\n"
EXPECTED_RX_BYTES = TRAMA_TELEMETRIA_TEXT.encode('utf-8')
EXPECTED_RX_LEN = len(EXPECTED_RX_BYTES)

# Ruta de guardado del reporte Excel
DOWNLOADS_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "reporte_recuperacion_enlace_usv.xlsx")

# ==============================================================================
# EJECUCIÓN DE PRUEBA DE RECUPERACIÓN (LINK RECOVERY TIME)
# ==============================================================================
def run_recovery_test():
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=0.01)
    except serial.SerialException as e:
        print(f"Error abriendo el puerto {PORT}: {e}")
        return

    rtt_list = []
    records = []
    
    # Variables de control de recuperación
    in_outage = False
    outage_start_time = 0.0
    consecutive_timeouts = 0
    recovery_events = []        # Almacena el tiempo de recuperación de cada evento (en ms)
    outage_durations = []       # Duraciones de cada corte de enlace
    
    lost_packets = 0
    received_packets = 0

    print(f"\n=== PRUEBA DE TIEMPO DE RECUPERACIÓN DE ENLACE USV (MODO BIDIRECCIONAL) ===")
    print(f"Puerto: {PORT} | Total Ciclos: {TOTAL_PACKETS} | Timeout: {TIMEOUT_SEC*1000:.0f} ms | Intervalo: {INTERVAL_SEC*1000:.0f} ms")
    print(f"Instrucción: Simule la desconexión desenchufando la antena/micro/cable o alejando el equipo.")
    print("-" * 105)

    ser.reset_input_buffer()
    ser.reset_output_buffer()
    test_start_time = time.time()

    for i in range(1, TOTAL_PACKETS + 1):
        loop_start_time = time.perf_counter()
        ser.reset_input_buffer()

        # 1. Transmitir comando de control $PUSVU
        t_start = time.perf_counter()
        ser.write(TX_BYTES)
        ser.flush()

        received = False
        rx_buffer = bytearray()

        # 2. Esperar respuesta de telemetría $PUSVD
        while (time.perf_counter() - t_start) < TIMEOUT_SEC:
            if ser.in_waiting > 0:
                rx_buffer.extend(ser.read(ser.in_waiting))
                
                header_idx = rx_buffer.find(b"$PUSVD")
                if header_idx != -1:
                    if header_idx > 0:
                        rx_buffer = rx_buffer[header_idx:]

                    if len(rx_buffer) >= EXPECTED_RX_LEN:
                        t_end = time.perf_counter()
                        rtt_ms = (t_end - t_start) * 1000.0
                        received = True
                        received_packets += 1
                        rtt_list.append(rtt_ms)

                        # --- EVALUACIÓN DE RECUPERACIÓN DE ENLACE ---
                        recovery_time_ms = 0.0
                        if in_outage:
                            # Se detecta el reenganche tras una desconexión
                            recovery_time_s = t_end - outage_start_time
                            recovery_time_ms = recovery_time_s * 1000.0
                            recovery_events.append(recovery_time_ms)
                            outage_durations.append(consecutive_timeouts * INTERVAL_SEC)
                            
                            print(f"\n>>> ¡ENLACE RECUPERADO EN CICLO {i:03d}! <<<")
                            print(f"    -> Tiempo Total de Recuperación: {recovery_time_ms:.2f} ms")
                            print(f"    -> Paquetes Consecutivos Perdidos: {consecutive_timeouts}\n")
                            
                            in_outage = False
                            consecutive_timeouts = 0

                        print(f"Ciclo {i:03d}: OK | RTT = {rtt_ms:.2f} ms | Estado: ENLACE ACTIVO")

                        records.append({
                            "Ciclo": i,
                            "Estado": "OK",
                            "RTT_ms": round(rtt_ms, 2),
                            "Timeouts_Consecutivos": 0,
                            "Tiempo_Recuperacion_ms": round(recovery_time_ms, 2) if recovery_time_ms > 0 else np.nan
                        })
                        break

        # --- EVALUACIÓN DE PÉRDIDA DE TRAMA / CAÍDA ---
        if not received:
            lost_packets += 1
            consecutive_timeouts += 1

            if not in_outage:
                # Inicio de un nuevo evento de pérdida de enlace
                in_outage = True
                outage_start_time = t_start

            print(f"Ciclo {i:03d}: TIMEOUT | Caída consecutiva #{consecutive_timeouts} | Estado: ENLACE CAÍDO")

            records.append({
                "Ciclo": i,
                "Estado": "TIMEOUT",
                "RTT_ms": np.nan,
                "Timeouts_Consecutivos": consecutive_timeouts,
                "Tiempo_Recuperacion_ms": np.nan
            })

        elapsed_loop = time.perf_counter() - loop_start_time
        if elapsed_loop < INTERVAL_SEC:
            time.sleep(INTERVAL_SEC - elapsed_loop)

    total_test_duration = time.time() - test_start_time
    ser.close()

    # ==============================================================================
    # INFORME Y CONSOLIDADO DE TIEMPO DE RECUPERACIÓN
    # ==============================================================================
    print("\n" + "="*95)
    print("      INFORME DE TIEMPOS DE RECUPERACIÓN DE ENLACE (LINK RECOVERY REPORT)")
    print("="*95)

    num_recovery_events = len(recovery_events)
    uptime_pct = (received_packets / TOTAL_PACKETS) * 100.0

    print(f"Puerto Serial Utilizado         : {PORT}")
    print(f"Ciclos Totales                  : {TOTAL_PACKETS}")
    print(f"Respuestas Correctas ($PUSVD)   : {received_packets} ({uptime_pct:.2f}% Disponibilidad)")
    print(f"Paquetes Perdidos Totales       : {lost_packets}")
    print(f"Eventos de Desconexión          : {num_recovery_events}")
    print("-" * 95)

    if recovery_events:
        print(f"Tiempo de Recuperación Promedio : {statistics.mean(recovery_events):.2f} ms")
        print(f"Tiempo de Recuperación Mínimo   : {min(recovery_events):.2f} ms")
        print(f"Tiempo de Recuperación Máximo   : {max(recovery_events):.2f} ms")
        print(f"Pérdida Consecutiva Promedio    : {statistics.mean(outage_durations):.2f} segundos")
    else:
        if lost_packets == 0:
            print("Tiempo de Recuperación          : N/A (El enlace nunca se cayó)")
        else:
            print("Tiempo de Recuperación          : N/A (El enlace cayó y no logró recuperarse antes de terminar)")

    print("-" * 95)

    # Exportación a Excel
    df_detalle = pd.DataFrame(records)
    
    resumen_data = {
        "Métrica": [
            "Puerto Serial", "Ciclos Totales", "Paquetes Recibidos OK", "Paquetes Perdidos", 
            "Disponibilidad Uptime (%)", "Eventos de Caída/Recuperación", 
            "Recuperación Promedio (ms)", "Recuperación Mínima (ms)", "Recuperación Máxima (ms)"
        ],
        "Valor": [
            PORT, TOTAL_PACKETS, received_packets, lost_packets,
            round(uptime_pct, 2), num_recovery_events,
            round(statistics.mean(recovery_events), 2) if recovery_events else "N/A",
            round(min(recovery_events), 2) if recovery_events else "N/A",
            round(max(recovery_events), 2) if recovery_events else "N/A"
        ]
    }
    df_resumen = pd.DataFrame(resumen_data)

    try:
        with pd.ExcelWriter(DOWNLOADS_PATH, engine='openpyxl') as writer:
            df_resumen.to_excel(writer, sheet_name='Resumen_Recuperacion', index=False)
            df_detalle.to_excel(writer, sheet_name='Detalle_Ciclos', index=False)
        print(f"Archivo Excel guardado con éxito en: {DOWNLOADS_PATH}\n")
    except Exception as e:
        print(f"Error al guardar Excel: {e}\n")

if __name__ == "__main__":
    run_recovery_test()
