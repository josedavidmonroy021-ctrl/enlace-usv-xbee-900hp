import serial
import time
import statistics
import os
import pandas as pd
import numpy as np

# ==============================================================================
# CONFIGURACIÓN OPTIMIZADA DE TIEMPOS (PRUEBA BIDIRECCIONAL AT)
# ==============================================================================
PORT = 'COM4'                   # Puerto Serie en Estación de Tierra
BAUD_RATE = 115200             # Baudrate
TOTAL_PACKETS = 120            # Cantidad total de ciclos de control/telemetría
SAMPLE_RSSI_EVERY = 30        # Mantener desactivado comandos AT por ahora
TIMEOUT_SEC = 0.8     #vf0.8 v3=2.0 v2=0.8 - v1=0.35 Tiempo máximo de espera por la trama de regreso ($PUSVD)
INTERVAL_SEC = 0.4  #vf0.4 v3=1.0 v2=0.35 v1=0.15 Intervalo entre envíos

# MACs del Enlace (Modo AT Transparente)
MAC_BASE = "0013A200419110BB"
MAC_USV = "0013A20041867349"

# 1. TRAMA DE SALIDA (Estación de Tierra -> USV) 32 bytes
TRAMA_CONTROL_TEXT = "$PUSVU,1500.0,1500.0,+00,01*42\r\n"
TX_BYTES = TRAMA_CONTROL_TEXT.encode('utf-8')

# 2. TRAMA DE ENTRADA ESPERADA (USV -> Estación de Tierra) - 128 Bytes exactos
TRAMA_TELEMETRIA_TEXT = "$PUSVD,102831.00,1024.7404,N,07531.9268,W,1,08,1.2,5.0,M,12.5,N,185.4,T,185.0,T,+1.2,P,-0.5,R,24.5,C,1,12.4,V,2.3,C,1,STATE,1*4F\r\n"

# Convertir a bytes exactos (128 bytes)
EXPECTED_RX_BYTES = TRAMA_TELEMETRIA_TEXT.encode('utf-8')
EXPECTED_RX_LEN = len(EXPECTED_RX_BYTES)  # 128 bytes

# Ruta de guardado en Excel (.xlsx) en Descargas
DOWNLOADS_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "reporte_bidireccional_at_usv.xlsx")

# ==============================================================================
# CÁLCULO DE BER (BIT ERROR RATE) Y DISTANCIA DE HAMMING
# ==============================================================================
def calculate_bit_errors(expected_bytes, received_bytes):
    """Compara byte a byte dos arreglos de bytes y calcula los bits erróneos."""
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
# CONSULTA DE MÉTRICAS RF EN MODO AT (GUARD TIME CONTROLADO)
# ==============================================================================
def obtener_rssi_snr_at(ser_port):
    """Consulta RSSI (ATDB) y Ruido (AT1S) asegurando los Guard Times requeridos."""
    time.sleep(1.1)  # Guard Time previo obligatorio
    ser_port.write(b'+++')
    time.sleep(1.1)  # Guard Time posterior obligatorio
    
    rssi_dbm = None
    noise_dbm = None
    
    if ser_port.in_waiting:
        resp = ser_port.read_all().decode('utf-8', errors='ignore')
        if 'OK' in resp:
            # 1. Consultar RSSI (ATDB)
            ser_port.write(b'ATDB\r')
            time.sleep(0.15)
            raw_rssi = ser_port.read_all().decode('utf-8', errors='ignore').strip()
            lines = [l.strip() for l in raw_rssi.split('\r') if l.strip() and l.strip() != 'OK']
            if lines:
                try:
                    rssi_dbm = -int(lines[-1], 16)
                except ValueError:
                    pass
            
            # 2. Consultar Ruido Ambiental (AT1S)
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
                
            # 3. Salir de modo AT
            ser_port.write(b'ATCN\r')
            time.sleep(0.2)
            ser_port.read_all()
            
    snr_db = (abs(noise_dbm) - abs(rssi_dbm)) if (rssi_dbm is not None and noise_dbm is not None) else None
    return rssi_dbm, noise_dbm, snr_db

# ==============================================================================
# EJECUCIÓN DE LA PRUEBA BIDIRECCIONAL (MASTER-SLAVE)
# ==============================================================================
def run_bidirectional_test():
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=0.01)
    except serial.SerialException as e:
        print(f"Error abriendo el puerto {PORT}: {e}")
        return

    rtt_list = []
    rssi_list = []
    snr_list = []
    throughput_list = []
    ber_list = []
    records = []
    
    lost_packets = 0
    corrupted_packets = 0
    total_bit_errors_accumulated = 0
    
    last_rssi, last_noise, last_snr = None, None, None
    
    print(f"\n=== PRUEBA BIDIRECCIONAL RF USV (MODO AT) [PUERTO: {PORT}] ===")
    print(f"Base MAC: {MAC_BASE} ---> USV STM32F411 MAC: {MAC_USV}")
    print(f"TX: Control $PUSVU ({len(TX_BYTES)} B) | RX Esperado: Telemetría $PUSVD ({EXPECTED_RX_LEN} B)")
    print("-" * 95)
    
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    test_start_time = time.time()
    
    for i in range(1, TOTAL_PACKETS + 1):
        loop_start_time = time.perf_counter()
        
        # Muestreo de parámetros RF en la Base cada SAMPLE_RSSI_EVERY paquetes
        if i == 1 or i % SAMPLE_RSSI_EVERY == 0:
            print(f"\n[INFO] Leyendo métricas RF vía Comandos AT en Base (Muestra #{i})...")
            last_rssi, last_noise, last_snr = obtener_rssi_snr_at(ser)
            print(f"       -> RSSI: {last_rssi} dBm | Ruido: {last_noise} dBm | SNR: {last_snr} dB\n")

        # Limpiar buffers antes de enviar nueva consulta
        ser.reset_input_buffer()

        # 1. Transmitir comando de control $PUSVU al STM32
        t_start = time.perf_counter()
        ser.write(TX_BYTES)
        ser.flush()
        
        received = False
        rx_buffer = bytearray()
        
        # 2. Esperar respuesta de telemetría $PUSVD del STM32
        while (time.perf_counter() - t_start) < TIMEOUT_SEC:
            if ser.in_waiting > 0:
                rx_buffer.extend(ser.read(ser.in_waiting))
                
                # Sincronizar: Buscar cabecera $PUSVD en el buffer
                header_idx = rx_buffer.find(b"$PUSVD")
                if header_idx != -1:
                    # Descartar basura previa al inicio de $PUSVD
                    if header_idx > 0:
                        rx_buffer = rx_buffer[header_idx:]
                    
                    # Verificar si ya llegaron los 128 bytes completos a partir de $PUSVD
                    if len(rx_buffer) >= EXPECTED_RX_LEN:
                        t_end = time.perf_counter()
                        rtt_ms = (t_end - t_start) * 1000.0
                        
                        rx_payload = bytes(rx_buffer[:EXPECTED_RX_LEN])
                        bit_errs, ber_pct = calculate_bit_errors(EXPECTED_RX_BYTES, rx_payload)
                        total_bit_errors_accumulated += bit_errs
                        if bit_errs > 0:
                            corrupted_packets += 1
                        
                        # Cálculo de Throughput bidireccional
                        total_cycle_bits = (len(TX_BYTES) + EXPECTED_RX_LEN) * 8
                        inst_throughput_kbps = total_cycle_bits / rtt_ms
                        
                        rtt_list.append(rtt_ms)
                        throughput_list.append(inst_throughput_kbps)
                        ber_list.append(ber_pct)
                        
                        if last_rssi is not None:
                            rssi_list.append(last_rssi)
                            snr_list.append(last_snr)
                            
                        received = True
                        rssi_str = f"{last_rssi} dBm" if last_rssi is not None else "N/A"
                        snr_str = f"{last_snr:.1f} dB" if last_snr is not None else "N/A"
                        
                        print(f"Ciclo {i:03d}: OK | RTT = {rtt_ms:.2f} ms | Throughput = {inst_throughput_kbps:.2f} kbps | RSSI = {rssi_str} | SNR = {snr_str} | BER RX = {ber_pct:.2f}%")
                        
                        records.append({
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
            print(f"Ciclo {i:03d}: TIMEOUT / SIN RESPUESTA STM32")
            records.append({
                "Paquete": i,
                "Estado": "TIMEOUT",
                "RTT_ms": np.nan,
                "Throughput_kbps": 0.0,
                "RSSI_dBm": np.nan,
                "SNR_dB": np.nan,
                "Errores_Bit": EXPECTED_RX_LEN * 8,
                "BER_Pct": 100.0
            })
            
        elapsed_loop = time.perf_counter() - loop_start_time
        if elapsed_loop < INTERVAL_SEC:
            time.sleep(INTERVAL_SEC - elapsed_loop)
        
    total_test_duration = time.time() - test_start_time
    ser.close()

    # ==============================================================================
    # CÁLCULO DE MÉTRICAS CONSOLIDADAS Y GENERACIÓN DE EXCEL
    # ==============================================================================
    print("\n" + "="*95)
    print("      INFORME CONSOLIDADO PRUEBA BIDIRECCIONAL USV (MODO AT)")
    print("="*95)
    
    if rtt_list:
        received_packets = len(rtt_list)
        packet_loss_pct = (lost_packets / TOTAL_PACKETS) * 100.0
        total_bits_expected = TOTAL_PACKETS * EXPECTED_RX_LEN * 8
        global_ber_pct = (total_bit_errors_accumulated / total_bits_expected) * 100.0 if total_bits_expected > 0 else 0.0
        
        jitter_diffs = [abs(rtt_list[k] - rtt_list[k-1]) for k in range(1, len(rtt_list))]
        jitter_ms = statistics.mean(jitter_diffs) if jitter_diffs else 0.0
        
        total_cycle_bits = (len(TX_BYTES) + EXPECTED_RX_LEN) * 8
        throughput_promedio_kbps = ((received_packets * total_cycle_bits) / 1000.0) / total_test_duration
        
        print(f"Puerto Serial Utilizado       : {PORT}")
        print(f"MAC Base / MAC STM32 USV      : {MAC_BASE} / {MAC_USV}")
        print(f"Ciclos Transmitidos           : {TOTAL_PACKETS}")
        print(f"Respuestas Telemetría OK      : {received_packets}")
        print(f"Paquetes Perdidos / Timeout   : {lost_packets} ({packet_loss_pct:.2f} %)")
        print(f"Paquetes Corruptos            : {corrupted_packets}")
        print(f"BER Global Telemetría         : {global_ber_pct:.4f} % ({total_bit_errors_accumulated} bits erróneos)")
        print(f"Throughput Enlace Promedio     : {throughput_promedio_kbps:.2f} kbps")
        print("-" * 95)
        print(f"Latencia Mínima               : {min(rtt_list):.2f} ms")
        print(f"Latencia Promedio (RTT)       : {statistics.mean(rtt_list):.2f} ms")
        print(f"Latencia Máxima               : {max(rtt_list):.2f} ms")
        print(f"Percentil 95 (P95)            : {np.percentile(rtt_list, 95):.2f} ms")
        print(f"Percentil 99 (P99)            : {np.percentile(rtt_list, 99):.2f} ms")
        print(f"Jitter (Variación Latencia)   : {jitter_ms:.2f} ms")
        print("-" * 95)
        if rssi_list:
            print(f"RSSI Promedio                 : {statistics.mean(rssi_list):.1f} dBm")
            print(f"RSSI Máximo / Mínimo          : {max(rssi_list)} dBm / {min(rssi_list)} dBm")
            print(f"SNR Promedio                  : {statistics.mean(snr_list):.1f} dB")
            print(f"SNR Máximo / Mínimo           : {max(snr_list):.1f} dB / {min(snr_list):.1f} dB")
        else:
            print("RSSI / SNR                    : No disponible")
            
        df_paquetes = pd.DataFrame(records)
        
        resumen_data = {
            "Métrica": [
                "Puerto Serial Base", "MAC Base", "MAC STM32 USV", "Ciclos Transmitidos", "Respuestas Telemetría OK", 
                "Paquetes Perdidos", "Tasa Pérdida (%)", "Paquetes Corruptos", "BER Global Telemetría (%)", 
                "Throughput Promedio (kbps)", "Latencia Mínima (ms)", "Latencia Promedio RTT (ms)", 
                "Latencia Máxima (ms)", "Percentil 95 P95 (ms)", "Percentil 99 P99 (ms)", "Jitter (ms)", 
                "RSSI Promedio (dBm)", "SNR Promedio (dB)"
            ],
            "Valor": [
                PORT, MAC_BASE, MAC_USV, TOTAL_PACKETS, received_packets, lost_packets, 
                round(packet_loss_pct, 2), corrupted_packets, round(global_ber_pct, 4), round(throughput_promedio_kbps, 2),
                round(min(rtt_list), 2), round(statistics.mean(rtt_list), 2), round(max(rtt_list), 2),
                round(np.percentile(rtt_list, 95), 2), round(np.percentile(rtt_list, 99), 2), round(jitter_ms, 2),
                round(statistics.mean(rssi_list), 1) if rssi_list else "N/A",
                round(snr_list[0], 1) if snr_list else "N/A"
            ]
        }
        df_resumen = pd.DataFrame(resumen_data)
        
        try:
            with pd.ExcelWriter(DOWNLOADS_PATH, engine='openpyxl') as writer:
                df_resumen.to_excel(writer, sheet_name='Resumen_Ejecutivo', index=False)
                df_paquetes.to_excel(writer, sheet_name='Detalle_Ciclos', index=False)
            print("="*95)
            print(f"Archivo Excel guardado con éxito en: {DOWNLOADS_PATH}")
            print("="*95)
        except Exception:
            csv_path = DOWNLOADS_PATH.replace('.xlsx', '.csv')
            df_paquetes.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print("="*95)
            print(f"Archivo CSV guardado en: {csv_path}")
            print("="*95)
    else:
        print("Error: Sin recepción de respuesta del STM32. Verifique la conexión serial del microcontrolador.")

if __name__ == "__main__":
    run_bidirectional_test()
