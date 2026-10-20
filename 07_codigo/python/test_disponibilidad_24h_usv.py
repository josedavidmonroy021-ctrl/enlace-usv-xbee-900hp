import serial
import time
import statistics
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURACIÓN GENERAL Y TIEMPO DE PRUEBA
# ==============================================================================
PORT = 'COM4'                   # Puerto Serie en Estación de Tierra
BAUD_RATE = 115200             # Baudrate
HOURS_TO_RUN = 24.0            # Duración de la prueba en HORAS (ej: 24.0, 12.0, 0.5)

SAMPLE_RSSI_EVERY = 500        # Muestreo AT cada N paquetes
TIMEOUT_SEC = 0.8             # Tiempo máximo de espera por trama de regreso ($PUSVD)
INTERVAL_SEC = 0.4            # Intervalo entre envíos (aprox. 6-7 paquetes/segundo)

# Umbral para Opción B: Mínimo de TIMEOUTS consecutivos para declarar caída real
MIN_TIMEOUTS_FOR_DISRUPTION = 3  

# MACs del Enlace (Modo AT Transparente)
MAC_BASE = "0013A200419110BB"
MAC_USV = "0013A20041867349"

# 1. TRAMA DE SALIDA (Estación de Tierra -> USV)
TRAMA_CONTROL_TEXT = "$PUSVU,1500.0,1500.0,+00,01*42\r\n"
TX_BYTES = TRAMA_CONTROL_TEXT.encode('utf-8')

# 2. TRAMA DE ENTRADA ESPERADA (USV -> Estación de Tierra) - 128 Bytes
TRAMA_TELEMETRIA_TEXT = "$PUSVD,102831.00,1024.7404,N,07531.9268,W,1,08,1.2,5.0,M,12.5,N,185.4,T,185.0,T,+1.2,P,-0.5,R,24.5,C,1,12.4,V,2.3,C,1,STATE,1*4F\r\n"
EXPECTED_RX_BYTES = TRAMA_TELEMETRIA_TEXT.encode('utf-8')
EXPECTED_RX_LEN = len(EXPECTED_RX_BYTES)

# Ruta de guardado en Excel (.xlsx) en Descargas
FILENAME_EXCEL = f"reporte_disponibilidad_{int(HOURS_TO_RUN)}h_usv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
DOWNLOADS_PATH = os.path.join(os.path.expanduser("~"), "Downloads", FILENAME_EXCEL)

# ==============================================================================
# CÁLCULO DE BER (BIT ERROR RATE) Y DISTANCIA DE HAMMING
# ==============================================================================
def calculate_bit_errors(expected_bytes, received_bytes):
    bit_errors = 0
    min_len = min(len(expected_bytes), len(received_bytes))
    for b1, b2 in zip(expected_bytes[:min_len], received_bytes[:min_len]):
        bit_errors += bin(b1 ^ b2).count('1')
    len_diff = abs(len(expected_bytes) - len(received_bytes))
    bit_errors += len_diff * 8
    total_bits = len(expected_bytes) * 8
    ber_pct = (bit_errors / total_bits) * 100.0 if total_bits > 0 else 0.0
    return bit_errors, ber_pct

# ==============================================================================
# CONSULTA DE MÉTRICAS RF EN MODO AT
# ==============================================================================
def obtener_rssi_snr_at(ser_port):
    time.sleep(1.1)
    ser_port.write(b'+++')
    time.sleep(1.1)
    rssi_dbm, noise_dbm = None, None
    
    if ser_port.in_waiting:
        resp = ser_port.read_all().decode('utf-8', errors='ignore')
        if 'OK' in resp:
            ser_port.write(b'ATDB\r')
            time.sleep(0.15)
            raw_rssi = ser_port.read_all().decode('utf-8', errors='ignore').strip()
            lines = [l.strip() for l in raw_rssi.split('\r') if l.strip() and l.strip() != 'OK']
            if lines:
                try:
                    val = int(lines[-1], 16)
                    if val > 0:  # Ignorar respuestas 0 no válidas de arranque
                        rssi_dbm = -val
                except ValueError:
                    pass
            
            ser_port.write(b'AT1S\r')
            time.sleep(0.15)
            raw_noise = ser_port.read_all().decode('utf-8', errors='ignore').strip()
            lines_n = [l.strip() for l in raw_noise.split('\r') if l.strip() and l.strip() != 'OK']
            if lines_n:
                try:
                    noise_dbm = -int(lines_n[-1], 16)
                except ValueError:
                    noise_dbm = -95
            else:
                noise_dbm = -95
                
            ser_port.write(b'ATCN\r')
            time.sleep(0.2)
            ser_port.read_all()
            
    snr_db = (abs(noise_dbm) - abs(rssi_dbm)) if (rssi_dbm is not None and noise_dbm is not None) else None
    return rssi_dbm, noise_dbm, snr_db

# ==============================================================================
# EJECUCIÓN DE LA PRUEBA CONTINUA DE DISPONIBILIDAD (OPCIÓN B)
# ==============================================================================
def run_availability_test():
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=0.01)
    except serial.SerialException as e:
        print(f"Error abriendo el puerto {PORT}: {e}")
        return

    duration_seconds = HOURS_TO_RUN * 3600.0
    end_target_time = time.time() + duration_seconds
    
    rtt_list, rssi_list, snr_list, throughput_list, ber_list, records = [], [], [], [], [], []
    recovery_events = []
    
    total_packets = 0
    lost_packets = 0
    corrupted_packets = 0
    total_bit_errors_accumulated = 0
    
    # Control de Estado de Caída y Recuperación (Opción B)
    consecutive_timeouts = 0
    in_disruption = False
    disruption_start_time = None
    max_consecutive_ok = 0
    current_consecutive_ok = 0
    
    last_rssi, last_noise, last_snr = None, None, None
    
    print("=" * 105)
    print(f"   PRUEBA CONTINUA DE DISPONIBILIDAD DE TELEMETRÍA USV ({HOURS_TO_RUN} HORAS) - OPCIÓN B")
    print("=" * 105)
    print(f"Puerto Base: {PORT} | MAC Base: {MAC_BASE} ---> MAC USV: {MAC_USV}")
    print(f"Filtro de Desconexión Real: Mínimo {MIN_TIMEOUTS_FOR_DISRUPTION} timeouts consecutivos (~{MIN_TIMEOUTS_FOR_DISRUPTION*(TIMEOUT_SEC+INTERVAL_SEC):.1f} s)")
    print(f"Hora de Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Hora Estimada de Finalización: {(datetime.now() + timedelta(hours=HOURS_TO_RUN)).strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 105)

    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    test_start_time = time.time()
    
    try:
        while time.time() < end_target_time:
            total_packets += 1
            i = total_packets
            loop_start_time = time.perf_counter()
            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            # Muestreo AT periódico
            if i == 1 or i % SAMPLE_RSSI_EVERY == 0:
                print(f"\n[{current_timestamp}] Leyendo métricas RF (Muestra #{i})...")
                last_rssi, last_noise, last_snr = obtener_rssi_snr_at(ser)
                rssi_p = f"{last_rssi} dBm" if last_rssi is not None else "En proceso..."
                snr_p = f"{last_snr:.1f} dB" if last_snr is not None else "En proceso..."
                print(f"       -> RSSI: {rssi_p} | Ruido: {last_noise} dBm | SNR: {snr_p}\n")

            ser.reset_input_buffer()
            t_start = time.perf_counter()
            ser.write(TX_BYTES)
            ser.flush()
            
            received = False
            rx_buffer = bytearray()
            
            # Recepción de trama
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
                            
                            rx_payload = bytes(rx_buffer[:EXPECTED_RX_LEN])
                            bit_errs, ber_pct = calculate_bit_errors(EXPECTED_RX_BYTES, rx_payload)
                            total_bit_errors_accumulated += bit_errs
                            if bit_errs > 0:
                                corrupted_packets += 1
                            
                            total_cycle_bits = (len(TX_BYTES) + EXPECTED_RX_LEN) * 8
                            inst_throughput_kbps = total_cycle_bits / rtt_ms
                            
                            rtt_list.append(rtt_ms)
                            throughput_list.append(inst_throughput_kbps)
                            ber_list.append(ber_pct)
                            
                            if last_rssi is not None:
                                rssi_list.append(last_rssi)
                                snr_list.append(last_snr)
                                
                            received = True
                            consecutive_timeouts = 0  # Reiniciar contador de fallos
                            current_consecutive_ok += 1
                            if current_consecutive_ok > max_consecutive_ok:
                                max_consecutive_ok = current_consecutive_ok
                            
                            # Si veníamos de una caída de energía/enlace REAL
                            if in_disruption:
                                recovery_time_sec = time.time() - disruption_start_time
                                in_disruption = False
                                recovery_events.append({
                                    "Fecha_Caida": datetime.fromtimestamp(disruption_start_time).strftime('%Y-%m-%d %H:%M:%S'),
                                    "Fecha_Recuperacion": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    "Tiempo_Recuperacion_Seg": round(recovery_time_sec, 2)
                                })
                                print(f"\n" + "!"*90)
                                print(f"!!! [ENLACE RESTABLECIDO TRAS CORTE REAL] Tiempo de Recuperación: {recovery_time_sec:.2f} segundos !!!")
                                print("!"*90 + "\n")

                            records.append({
                                "Timestamp": current_timestamp,
                                "Paquete": i,
                                "Estado": "OK",
                                "RTT_ms": round(rtt_ms, 2),
                                "Throughput_kbps": round(inst_throughput_kbps, 2),
                                "RSSI_dBm": last_rssi if last_rssi is not None else np.nan,
                                "SNR_dB": round(last_snr, 2) if last_snr is not None else np.nan,
                                "Errores_Bit": bit_errs,
                                "BER_Pct": round(ber_pct, 4)
                            })
                            break
            
            if not received:
                lost_packets += 1
                consecutive_timeouts += 1
                current_consecutive_ok = 0
                
                # Opción B: Declarar caída real solo tras alcanzarse MIN_TIMEOUTS_FOR_DISRUPTION
                if consecutive_timeouts >= MIN_TIMEOUTS_FOR_DISRUPTION and not in_disruption:
                    in_disruption = True
                    # El tiempo de inicio del corte se fija cuando comenzó el primer timeout consecutivo
                    disruption_start_time = time.time() - ((MIN_TIMEOUTS_FOR_DISRUPTION - 1) * (TIMEOUT_SEC + INTERVAL_SEC))
                    print(f"\n[ALERTA CAÍDA REAL DETECTADA] Transcurridos {consecutive_timeouts} timeouts seguidos sin energía/enlace...")
                
                records.append({
                    "Timestamp": current_timestamp,
                    "Paquete": i,
                    "Estado": "TIMEOUT",
                    "RTT_ms": np.nan,
                    "Throughput_kbps": 0.0,
                    "RSSI_dBm": np.nan,
                    "SNR_dB": np.nan,
                    "Errores_Bit": EXPECTED_RX_LEN * 8,
                    "BER_Pct": 100.0
                })
            
            # Progreso
            if i % 100 == 0 or (consecutive_timeouts >= MIN_TIMEOUTS_FOR_DISRUPTION):
                disponibilidad_inst = ((i - lost_packets) / i) * 100.0
                state_str = "OK" if received else f"TIMEOUT ({consecutive_timeouts} seguidos)"
                rtt_disp = f"{rtt_list[-1]:.2f} ms" if received else "N/A"
                print(f"[{current_timestamp}] Pkt {i:06d}: {state_str} | RTT = {rtt_disp} | Disp. Acumulada = {disponibilidad_inst:.3f}%")
                
            elapsed_loop = time.perf_counter() - loop_start_time
            if elapsed_loop < INTERVAL_SEC:
                time.sleep(INTERVAL_SEC - elapsed_loop)

    except KeyboardInterrupt:
        print("\nPrueba interrumpida manualmente por el usuario. Generando informe parcial...")

    total_test_duration = time.time() - test_start_time
    ser.close()

    # ==============================================================================
    # CÁLCULO DE MÉTRICAS CONSOLIDADAS Y GENERACIÓN DE EXCEL
    # ==============================================================================
    received_packets = len(rtt_list)
    disponibilidad_pct = (received_packets / total_packets) * 100.0 if total_packets > 0 else 0.0
    packet_loss_pct = (lost_packets / total_packets) * 100.0 if total_packets > 0 else 0.0
    
    total_bits_expected = total_packets * EXPECTED_RX_LEN * 8
    global_ber_pct = (total_bit_errors_accumulated / total_bits_expected) * 100.0 if total_bits_expected > 0 else 0.0
    
    jitter_diffs = [abs(rtt_list[k] - rtt_list[k-1]) for k in range(1, len(rtt_list))] if len(rtt_list) > 1 else []
    jitter_ms = statistics.mean(jitter_diffs) if jitter_diffs else 0.0
    
    total_cycle_bits = (len(TX_BYTES) + EXPECTED_RX_LEN) * 8
    throughput_promedio_kbps = ((received_packets * total_cycle_bits) / 1000.0) / total_test_duration if total_test_duration > 0 else 0.0
    
    rec_times = [r["Tiempo_Recuperacion_Seg"] for r in recovery_events]
    mean_recovery_sec = statistics.mean(rec_times) if rec_times else 0.0
    max_recovery_sec = max(rec_times) if rec_times else 0.0
    
    downtime_est_sec = lost_packets * (TIMEOUT_SEC + INTERVAL_SEC)
    uptime_est_sec = max(0.0, total_test_duration - downtime_est_sec)

    print("\n" + "=" * 105)
    print("      INFORME DE DISPONIBILIDAD Y RENDIMIENTO DEL ENLACE USV (24H+)")
    print("=" * 105)
    print(f"El enlace presentó una disponibilidad de {disponibilidad_pct:.2f} % durante una prueba continua de {total_test_duration/3600.0:.2f} horas.")
    print("-" * 105)
    print(f"Duración Total de Prueba      : {timedelta(seconds=int(total_test_duration))} (hh:mm:ss)")
    print(f"Tiempo Operativo (Uptime)     : {timedelta(seconds=int(uptime_est_sec))}")
    print(f"Tiempo Fuera de Servicio      : {downtime_est_sec:.2f} segundos")
    print(f"Disponibilidad del Enlace     : {disponibilidad_pct:.4f} %")
    print(f"Total Paquetes Transmitidos   : {total_packets}")
    print(f"Paquetes Recibidos Correctos  : {received_packets}")
    print(f"Paquetes Perdidos / Timeout   : {lost_packets} ({packet_loss_pct:.2f} %)")
    print(f"Cortes de Energía/Enlace Reales: {len(recovery_events)}")
    if recovery_events:
        print(f"Tiempo Prom. de Recuperación : {mean_recovery_sec:.2f} segundos")
        print(f"Tiempo Máx. de Recuperación  : {max_recovery_sec:.2f} segundos")
    print(f"Racha Máx. Enlace Continuo    : {max_consecutive_ok} paquetes OK seguidos")
    print("-" * 105)
    print(f"Throughput Enlace Promedio    : {throughput_promedio_kbps:.2f} kbps")
    print(f"BER Global Telemetría        : {global_ber_pct:.4f} %")
    if rtt_list:
        print(f"Latencia Promedio RTT        : {statistics.mean(rtt_list):.2f} ms")
        print(f"Latencia Mín / Máx           : {min(rtt_list):.2f} ms / {max(rtt_list):.2f} ms")
        print(f"Jitter (Variación Latencia)  : {jitter_ms:.2f} ms")
    if rssi_list:
        print(f"RSSI Promedio                : {statistics.mean(rssi_list):.1f} dBm")
        print(f"SNR Promedio                 : {statistics.mean(snr_list):.1f} dB")
    print("=" * 105)

    # Exportar a Excel
    df_paquetes = pd.DataFrame(records)
    df_recuperacion = pd.DataFrame(recovery_events) if recovery_events else pd.DataFrame(columns=["Fecha_Caida", "Fecha_Recuperacion", "Tiempo_Recuperacion_Seg"])

    resumen_data = {
        "Métrica de Disponibilidad y Enlace": [
            "Puerto Serial Base", "MAC Base", "MAC STM32 USV",
            "Horas Programadas", "Duración Total Real (hh:mm:ss)", "Disponibilidad del Enlace (%)",
            "Tiempo Operativo Est. (seg)", "Tiempo Fuera de Servicio Est. (seg)",
            "Total Ciclos Transmitidos", "Respuestas Telemetría OK", "Paquetes Perdidos / Timeout",
            "Tasa Pérdida de Paquetes (%)", "Cortes Reales de Enlace/Energía", "Tiempo Promedio de Recuperación (seg)",
            "Tiempo Máximo de Recuperación (seg)", "Racha Máxima Conexión Continua (Pkts OK)",
            "Paquetes Corruptos (Bit Errors)", "BER Global Telemetría (%)", "Throughput Promedio (kbps)",
            "Latencia Mínima RTT (ms)", "Latencia Promedio RTT (ms)", "Latencia Máxima RTT (ms)",
            "Percentil 95 P95 RTT (ms)", "Percentil 99 P99 RTT (ms)", "Jitter Latencia (ms)",
            "RSSI Promedio (dBm)", "SNR Promedio (dB)"
        ],
        "Valor": [
            PORT, MAC_BASE, MAC_USV,
            HOURS_TO_RUN, str(timedelta(seconds=int(total_test_duration))), round(disponibilidad_pct, 4),
            round(uptime_est_sec, 2), round(downtime_est_sec, 2),
            total_packets, received_packets, lost_packets,
            round(packet_loss_pct, 2), len(recovery_events), round(mean_recovery_sec, 2),
            round(max_recovery_sec, 2), max_consecutive_ok,
            corrupted_packets, round(global_ber_pct, 4), round(throughput_promedio_kbps, 2),
            round(min(rtt_list), 2) if rtt_list else "N/A",
            round(statistics.mean(rtt_list), 2) if rtt_list else "N/A",
            round(max(rtt_list), 2) if rtt_list else "N/A",
            round(np.percentile(rtt_list, 95), 2) if rtt_list else "N/A",
            round(np.percentile(rtt_list, 99), 2) if rtt_list else "N/A",
            round(jitter_ms, 2),
            round(statistics.mean(rssi_list), 1) if rssi_list else "N/A",
            round(statistics.mean(snr_list), 1) if snr_list else "N/A"
        ]
    }
    df_resumen = pd.DataFrame(resumen_data)

    try:
        with pd.ExcelWriter(DOWNLOADS_PATH, engine='openpyxl') as writer:
            df_resumen.to_excel(writer, sheet_name='Resumen_Disponibilidad', index=False)
            df_recuperacion.to_excel(writer, sheet_name='Tiempos_Recuperacion', index=False)
            df_paquetes.to_excel(writer, sheet_name='Detalle_Ciclos_Continuos', index=False)
        print(f"\nReporte Excel generado exitosamente en: {DOWNLOADS_PATH}\n")
    except Exception as e:
        csv_path = DOWNLOADS_PATH.replace('.xlsx', '.csv')
        df_paquetes.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\nGenerado CSV alternativo en: {csv_path} (Error openpyxl: {e})\n")

if __name__ == "__main__":
    run_availability_test()
