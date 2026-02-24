# BorderBot

 - Bot de simulación de trading de criptomonedas.
 - Atento a los precios así como un border collie vigilando ovejas.

## Descargo de responsabilidad

El mercado de criptomonedas es impredecible y arriesgado (así como cualquier forma de inversión).
Lo presentado en este proyecto no es recomendación de inversión.
Solamente comparto una herramienta de trading.
Usted debe ser cauteloso con esta herramienta o con cualquier otra.

## Canal de Odysee (alternativa a YouTube)

Le invito a seguirme en mi canal https://odysee.com/$/invite/@EspeculadorFinanciero:7
Allí hay explicaciones más detalladas del bot.

## Explicación de "borderbot.py" y "client.py"

Cuando simula trading en tiempo real ("borderbot.py") o hace backtesting ("client.py").
El bot selecciona la estrategia que supuestamente está teniendo mejor profit o menor loss (la variable "pl").

La fee se calcula en base a una fee mínima más un promedio y dando cierta prioridad a la volatilidad más reciente.

## Explicación de la estrategia BorderStrategy

El bot genera estrategias con configuraciones aleatorias.

Cada estrategia que se llama 'bs, ...', es del tipo BorderStrategy.
Por el momento es la única estrategia que hay en el bot.

Esta estrategia no tiene un take profit normal, sino que el stop loss se va ajustando a medida que pasa el tiempo y conforme a determinadas variables.
La idea es que el riesgo se reduzca con el tiempo y que (si sale bien) el stop loss esté cada vez mejor posicionado para dar mayor ganancia o menor pérdida.

La estrategia aumenta el apalancamiento de los longs a medida que los últimos longs tuvieron profit, así también con los shorts.
En caso contrario, lo disminuye.

Cada estrategia comienza con un short por defecto.

El stop loss estará por encima del precio de entrada, basado en la variable "sl_initial_dif".
A medida que el precio baje, el stop loss se modificara para estar al menor_precio_del_trade * (1 + "sl_initial_dif")

Si el stop loss llega a estar por debajo del stop_loss_inicial + "sl_reduced_dif", en vez de ajustarse por "sl_initial_dif", se ajustará por "sl_dif".

La variable "zoom" aumenta con los trades exitosos y disminuye en caso contrario. Similar a como sucede con el apalancamiento.

La variable "m_aprox" junto con el "zoom" actual disminuye la diferencia (sea de "sl_initial_dif" o de "sl_dif").
Esto es para que el riesgo se disminuya rápidamente cuando se está operando con apalancamiento.

## Prerrequisitos
  - Los paquetes de BeautifulSoup y psutil para Python 3.
  - Opcionalmente, Cython

## Instalación
 1.
```
git clone https://github.com/leoNoguera/borderbot.git
```
 2. Instalar BeautifulSoup, psutil y cython para Python3
 3. Opcionalmente, ejecutar: python3 setup.py build_ext --inplace

## Funcionalidades
  - [Configuración del bot](#config.json)
  - [Obtención de precios y ejecución de la simulación en tiempo real](#borderbot.py)
  - [Servidor](#server.py)
  - [Cliente](#client.py)
  - [Donaciones](#donaciones)

## config.json
Configuración de ejemplo:
```
{
	"pair" : "DRIFT-USDT", -> Par de activos por defecto
	"simulate_trading" : true, -> Simular trading en tiempo real o sólamente guardar precios
	"price_source" : "jupiter", -> De dónde se obtendrán los precios (por ahora sólamente admite la API gratuita de Jupiter)
	"timer" : 10, -> El tiempo, expresado en segundos, cada cuanto se leeran los precios
	"prices_gap_tolerance_seconds" : 300, -> Se usa en caso de haber un corte en la lectura de precios (por detener el bot, por problemas de conexión, etc.). Si hay un gap que supere la cantidad seleccionada, el bot no hará cambios en las operaciones (ni abrir ni cerrar) al hacer backtesting durante ese periodo de tiempo.
	"min_balance" : 1,
	"DRIFT-USDT" : { -> La configuración específica para el par seleccionado
		"id" : "DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7", -> La dirección del contrato del token en la red de Solana
		"decimals" : 16, -> La cantidad de decimales máxima al calcular los precios de dicho activo
		"dif_tolerance" : 0.1, -> Se usa para cuando en Jupiter las direrencias de precios son demasiado diferentes a los precios reales (a veces sucede). Por ejemplo, si se supera la diferencia promedio calculada más el 0.05 (equivalente al 5%), el bot no tendrá en cuenta los precios hasta que la diferencia sea menor al límite
		"first_timestamp" : 1716763935, "dif_tolerance" : 0.1, "last_dif_timestamp" : 0, -> En relación a lo anterior. Se usa para cuando hay diferencias de precios superiores al diferencia promedio más "dif_tolerance", pero realistas (cuando hay mucha más volatilidad de lo normal).

		-> Estas variables se usan cuando se elije una configuración aleatoria para la próxima estrategia durante el backtesting
		"random_var_add_less_priority" : 12, -> Cuando la última mejor estrategia disminuyó el valor de determinada variable respecto a la anterior, se añade determinada cantidad de -1 a la lista para dar mayor probabilidad que la nueva estrategia a probar vuelva a disminuir la variable en cuestión
		"random_var_default_less_priority" : 1, -> Da mayor probabilidad (por defecto) de disminuir la variable
		"random_var_equal_priority" : 5, -> Mantener la variable con el mismo valor
		"random_var_default_more_priority" : 1, -> Aumentar la variable
		"random_var_add_more_priority" : 12, -> Aumentar la variable luego de un aumento previo

		"sl_s_dif" : 0.18401, -> La diferencia que se aplica entre el precio actual y el stop loss en un short, en el caso de que el stop loss actual supere "sl_reduced_dif"
		"sl_l_dif" : 0.24468, -> Lo mismo pero con long
		"sl_dif_min" : 0.0001,
		"sl_dif_max" : 0.255,
		"sl_dif_decimals" : 5,

		"sl_reduced_dif_s" : 0.00001,
		"sl_reduced_dif_l" : 0.00006,
            -> Si el stop loss supera esa diferencia (respecto al stop loss inicial), procederá a usar "sl_dif"
		"sl_reduced_dif_min" : 0.00001,
		"sl_reduced_dif_max" : 0.2,
		"sl_reduced_dif_decimals" : 5,

		"sl_initial_dif_s" : 0.02548,
        "sl_initial_dif_l" : 0.001,
            -> La diferencia que se aplica al principio entre el precio actual y el stop loss, en el caso de que el stop loss actual no supere "sl_reduced_dif"
		"sl_initial_dif_min" : 0.001,
		"sl_initial_dif_max" : 0.03,
		"sl_initial_dif_decimals" : 5,

		"okno_inc_s" : 1.71272,
		"okno_inc_l" : 1.69741,
            -> Determina el incremento de l_ok o l_no, ambas son acumuladores. La primera influye en el incremento apalancamiento y la segunda en el decremento del apalancamiento
		"okno_inc_min" : 0.00001,
		"okno_inc_max" : 1.8,
		"okno_inc_decimals" : 5,

		"okno_dec_s" : 0.00002,
		"okno_dec_l" : 0.70928,
            -> Determina el decremento de l_ok o l_no
		"okno_dec_min" : 0.00002,
		"okno_dec_max" : 3.6,
		"okno_dec_decimals" : 5,

		"m_aprox_s" : 1599.9388566587,
		"m_aprox_l" : 0.0129437728,
            -> Determina (junto con otras variables) cuánto va a aproximarse el stop loss (con el paso del tiempo) al precio actual (en caso de haber "zoom")
		"m_aprox_min" : 0,
		"m_aprox_max" : 1600,
		"m_aprox_decimals" : 10,

		"leverage_inc_s" : 20.98176,
		"leverage_inc_l" : 9.09106,
            -> Determina (junto con otras variables) cuánto va a aumentar el apalancamiento (y el zoom) en caso de un trade exitoso (con profit)
		"leverage_inc_min" : 0.00001,
		"leverage_inc_max" : 21,
		"leverage_inc_decimals" : 5,

		"leverage_dec_s" : 41.48812,
		"leverage_dec_l" : 0.02373,
            -> Determina (junto con otras variables) cuánto va a decrementar el apalancamiento (y el zoom) en caso de un trade no exitoso (con pérdida)
		"leverage_dec_min" : 0.00002,
		"leverage_dec_max" : 42,
		"leverage_dec_decimals" : 5,

		"high_leverage_s" : 20,
		"high_leverage_l" : 20,
            -> El apalancamiento máximo
		"high_leverage_min" : 1,
		"high_leverage_max" : 20,
		"high_leverage_decimals" : 0,

		"far_price_dif_s" : 0.00688,
		"far_price_dif_l" : 0.00267,
            -> En 'strategy derivatives', determina la diferencia mínima que se necesita para cambiar de trade.
		"far_price_dif_min" : 0.00001,
		"far_price_dif_max" : 0.025,
		"far_price_dif_decimals" : 5,

		"min_fee" : 0.0031, -> La fee mínima que se aplicará para cada trade
		"fee_multiplier" : 92, -> Multiplica a la volatilidad de subidas o bajadas
		"last_up_down_priority" : 20, -> La prioridad que tendrá el último movimiento del precio al momento de calcular la fee
		"last_pl_priority" : 2, -> La prioridad del pl del trade actual respecto al promedio
        "derivatives" : [ -> Son variantes de la estrategia. Varían los momentos de entrada o salida de los trades respecto a la estrategia en cuestión.
            {"position" : "close", "coin2_balance" : 1, "leverage" : 1, "wait_zoom" : false, "wait_far_price_dif" : true, "far_price_dif_s" : null, "far_price_dif_l" : null, "total_investment" : 1, "open_price" : null, "close_on_close" : true},
            {"position" : "close", "coin2_balance" : 1, "leverage" : 1, "wait_zoom" : false, "wait_far_price_dif" : false, "total_investment" : 1, "open_price" : null, "close_on_close" : false}
        ]
	}
}
```


## borderbot.py

Para almacenar los precios de un par de activos en archivos:
```
python3 borderbot.py DRIFT-USDT 0 start
```

Para almacenar los precios de un par de activos en archivos y además simular trading en tiempo real:
```
python3 borderbot.py DRIFT-USDT 1 start
```

Usted verá que al ejecutar 'borderbot.py' o client.py' verá lineas con algo similar a:

strategy derivatives, long, far_price_dif ...
strategy derivatives, long, zoom >= ...

Estas son variantes de la estrategia que se está usando en ese momento.
Se utilizan las variables 'far_price_dif' o 'zoom' para indicar el momento de apertura del long o del short de la estrategia.

## server.py

Iniciar el servidor para backtesting:
```
python3 server.py 7010
```
El número corresponde al puerto que usará el servidor.

## client.py

Iniciar el cliente para backtesting:
```
python3 client.py DRIFT-USDT 1 localhost 7010
```
Los parámetros son: par 1 host puerto

## donaciones

Faltan muchas modificaciones en el proyecto y también una explicación más clara de la estrategia y del bot en general.

Si lo desea puede hacer una donación opcional, voluntaria y libre para apoyarme en este proyecto:

SOL:
1J42ZRiY7CdZ57QwuhPfRXb99fyNhnYoBtYqGuB8PRe

BNB, POL, ETH:
0x25B5c3123512d0c89050C9328121F1619E89590A
