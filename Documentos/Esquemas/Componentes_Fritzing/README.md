# COMPONENTES PARA FRITZING - ESTACAO METEOROLOGICA

Este pacote contem arquivos individuais .fzpz (pecas importaveis no Fritzing), nao um circuito .fzz.

* DHT22 = DHT22 Humidity and Temperature Sensor.fzpz
* ESP32 = DOIT Esp32 DevKit v1 improved.fzpz
* LDR = LM393 LDR breakout.fzpz
* BM280 = GY-BMEP280 Barometric Pressure Sensor - Breakout.fzpz (placa roxa com 6 pinos; verificar se e BMP280 ou BME280 no hardware)
* MQ-135 = MQ-135 Sensor Module.fzpz
* FONTE = YwRobot Breadboard Power Supply.fzpz

COMO USAR:
importe cada .fzpz em Part > Import (ou arraste para a biblioteca). Para compartilhar o circuito desenhado, use o arquivo .fzz do projeto.

ATENCAO: os arquivos sao representacoes graficas de pecas. A correspondencia dos terminais e tensoes com os modulos reais deve ser conferida antes da montagem fisica. O modulo MQ-135 pode produzir tensao analogica acima do limite suportado pelos GPIOs do ESP32.
