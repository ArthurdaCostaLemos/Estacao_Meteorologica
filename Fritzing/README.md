# Montagem da estação no Fritzing
O arquivo .fzz.zip, que deve ser descompactado, contém o projeto editável. As exportações JPEG mostram a vista do protoboard utilizada no relatório e na apresentação.

A montagem representa ESP32 DevKit V1 de 30 pinos, DHT22, BMP280 de seis pinos, módulo LDR e módulo MQ-135. A fonte desenhada é um modelo visual equivalente à HW-131, com as linhas identificadas em 5 V e 3,3 V e referência GND comum.

* DHT22: DATA na GPIO4; um resistor de 10 kΩ entre DATA e 3,3 V.
* BMP280: SDA na GPIO21 e SCL na GPIO22;
* LDR: AO na GPIO35; DO desconectado;
* MQ-135: AO → 10 kΩ → ponto GPIO34 → 20 kΩ → GND; DO desconectado;
* Alimentação: 5 V no VCC do MQ-135; 3,3 V nos demais sensores.

O [PDF da montagem] e da pinagem inclui a figura ampliada e os complementos de hardware. A vista de protoboard documenta as conexões; não constitui simulação eletrônica dos sensores.
