/*
 * UARTRX1.C
 *
 *  Created on: Apr 9, 2025
 *      Author: ALCIDES_RAMOS
 */

#ifndef LIBRERIAS_UARTRX1_C_
#define LIBRERIAS_UARTRX1_C_
#include "UARTRX.h"
#include "string.h"
#include "stdio.h"
#include "stdlib.h"


//DEFINE LOS USART  A USAR
extern UART_HandleTypeDef huart1;
//extern UART_HandleTypeDef huart2;

//inciar uart de recepcion por interrupcion  y tamaño del buffer
UARTRXS UARTRX1 = {&huart1,USART1,500};



//*********************************************************
//se llama solo una vez para  crear el buffer trama rx del usart deseado
void uartRX_it_idle_dma_init(UARTRXS *SERIAL)
{
// Asigna memoria
SERIAL->trama_rx = malloc(SERIAL->sizeT);  //reserva memoria
 memset(SERIAL->trama_rx,0,SERIAL->sizeT-1);//limpia el  buffer
 SERIAL->flag_rx=0;// LIMPIA LA BANDERA
__HAL_UART_CLEAR_OREFLAG(SERIAL->huart); // Limpia Overrun Error
__HAL_UART_FLUSH_DRREGISTER(SERIAL->huart); // Limpia buffer de entrada
 HAL_UARTEx_ReceiveToIdle_DMA(SERIAL->huart, (uint8_t*)SERIAL->trama_rx, SERIAL->sizeT);//inica la recepcion por idle
__HAL_DMA_DISABLE_IT(SERIAL->huart->hdmarx, DMA_IT_HT); // deshabilita HT, deja activo IDLE + buffer lleno

}



//si ya se creo el buffer trama rx  usar solo este
void  uartRX_DMA_Re_init(UARTRXS *SERIAL)
{

	memset(SERIAL->trama_rx,0,SERIAL->sizeT-1);//limpia el  buffer

	SERIAL->flag_rx=0;// LIMPIA LA BANDERA
__HAL_UART_CLEAR_OREFLAG(SERIAL->huart); // Limpia Overrun Error
__HAL_UART_FLUSH_DRREGISTER(SERIAL->huart); // Limpia buffer de entrada
 HAL_UARTEx_ReceiveToIdle_DMA(SERIAL->huart, (uint8_t*)SERIAL->trama_rx, SERIAL->sizeT);//inica la recepcion por idle
__HAL_DMA_DISABLE_IT(SERIAL->huart->hdmarx, DMA_IT_HT); // deshabilita HT, deja activo IDLE + buffer lleno
}

void uartRX_INTERRUPT(UART_HandleTypeDef *huart,uint16_t sizex)
{

	//colocar una por cada usart usado
	if ((UARTRX1.flag_rx==0)&& (huart->Instance == UARTRX1.usart_instance))//si es el uart de datos
		{
	     UARTRX1.num_datos=sizex;
	     UARTRX1.flag_rx=1;
		 }

//colocar si usa mas uart
		 /*
	if ((UARTRX2.flag_rx==0)&& (huart->Instance == UARTRX2.usart_instance))//si es el uart de datos
		{
	 // __HAL_UART_DISABLE_IT(huart, UART_IT_IDLE);
       HAL_UART_DMAStop(UARTRX2.huart);  //para la recepcion temporarmente
	     UARTRX2.num_datos=sizex;
	     UARTRX2.flag_rx=1;
		 }
*/
}

 void uartRX_Errores(UART_HandleTypeDef *huart)
 {
//colocar una por cada usart usado
	if (huart->Instance == UARTRX1.usart_instance)//si es el uart de datos
		{
		__HAL_UART_CLEAR_OREFLAG(UARTRX1.huart); // Limpia Overrun Error
        __HAL_UART_FLUSH_DRREGISTER(UARTRX1.huart); // Limpia buffer de entrada

		  if(UARTRX1.flag_rx==0)
		{
		HAL_UART_DMAStop(UARTRX1.huart);  //para la recepcion temporarmente
		HAL_UARTEx_ReceiveToIdle_DMA(UARTRX1.huart, (uint8_t*)UARTRX1.trama_rx, UARTRX1.sizeT);//inica la recepcion por idle
		__HAL_DMA_DISABLE_IT(UARTRX1.huart->hdmarx, DMA_IT_HT); // deshabilita HT, deja activo IDLE + buffer lleno

		}
	  }
//si usa otro usart
/*
	 	if (huart->Instance == UARTRX2.usart_instance)//si es el uart de datos
		{
		__HAL_UART_CLEAR_OREFLAG(UARTRX2.huart); // Limpia Overrun Error
        __HAL_UART_FLUSH_DRREGISTER(UARTRX2.huart); // Limpia buffer de entrada

		  if(UARTRX2.flag_rx==0)
		{
		HAL_UART_DMAStop(UARTRX2.huart);  //para la recepcion temporarmente
		HAL_UARTEx_ReceiveToIdle_DMA(UARTRX2.huart, (uint8_t*)UARTRX2.trama_rx, UARTRX2	.sizeT);//inica la recepcion por idle
		__HAL_DMA_DISABLE_IT(UARTRX2.huart->hdmarx, DMA_IT_HT); // deshabilita HT, deja activo IDLE + buffer lleno

		}
	  } 
*/

 }

#endif /* LIBRERIAS_UARTRX1_C_ */


void procesa_rx()
{
//variable para procesar inf
	char procesa[500];
	if (strstr(UARTRX1.trama_rx,"$PUSV")) 
	{
		strcpy(procesa,UARTRX1.trama_rx);
		
		const char *trama_telemetria = "$PUSVD,102831.00,1024.7404,N,07531.9268,W,1,08,1.2,5.0,M,12.5,N,185.4,T,185.0,T,+1.2,P,-0.5,R,24.5,C,1,12.4,V,2.3,C,1,STATE,1*4F\r\n";

// Enviar usando strlen() -> Transmite exactamente los 128 bytes reales sin basura
HAL_UART_Transmit(&huart1, (uint8_t*)trama_telemetria, strlen(trama_telemetria), 100); // TIMEOUT 100ms mide el tiempo de transmision, 100 ms es suficiente para 128 bytes a 115200 bps, pero si vas a transmitir más datos, ajusta el timeout según sea necesario, si aumento los bytes a transmitir, aumentar el timeout, por ejemplo, para 256 bytes a 115200 bps, un timeout de 200 ms sería adecuado.Timeout es cada cuanto se espera que la transmision se complete, si no se completa en ese tiempo, la funcion retorna error.
// timeout es el tiempo maximo que la funcion espera a que se complete la transmision, si no se completa en ese tiempo, retorna error.
	}
	

}



