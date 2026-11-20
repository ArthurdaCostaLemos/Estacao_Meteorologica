import time
from micropython import const

BMP280_I2C_ADDR = const(0x76)

class BMP280:
    def _init_(self, i2c, addr=BMP280_I2C_ADDR):
        self.i2c = i2c
        self.addr = addr
        self._load_calibration()
        # Modo normal, oversampling x1 temp/pressão
        self.i2c.writeto_mem(self.addr, 0xF4, b'\x27')
        self.i2c.writeto_mem(self.addr, 0xF5, b'\xA0')
        time.sleep_ms(50)

    def _read_u16(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 2)
        return data[0] | (data[1] << 8)

    def _read_s16(self, reg):
        val = self._read_u16(reg)
        return val - 65536 if val > 32767 else val

    def _load_calibration(self):
        self.dig_T1 = self._read_u16(0x88)
        self.dig_T2 = self._read_s16(0x8A)
        self.dig_T3 = self._read_s16(0x8C)
        self.dig_P1 = self._read_u16(0x8E)
        self.dig_P2 = self._read_s16(0x90)
        self.dig_P3 = self._read_s16(0x92)
        self.dig_P4 = self._read_s16(0x94)
        self.dig_P5 = self._read_s16(0x96)
        self.dig_P6 = self._read_s16(0x98)
        self.dig_P7 = self._read_s16(0x9A)
        self.dig_P8 = self._read_s16(0x9C)
        self.dig_P9 = self._read_s16(0x9E)

    def read(self):
        data = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_T = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)

        var1 = (((adc_T >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = (((((adc_T >> 4) - self.dig_T1) * ((adc_T >> 4) - self.dig_T1)) >> 12) * self.dig_T3) >> 14
        t_fine = var1 + var2
        temp = ((t_fine * 5 + 128) >> 8) / 100.0

        var1 = t_fine - 128000
        var2 = var1 * var1 * self.dig_P6
        var2 = var2 + ((var1 * self.dig_P5) << 17)
        var2 = var2 + (self.dig_P4 << 35)
        var1 = ((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) << 12)
        var1 = (((1 << 47) + var1) * self.dig_P1) >> 33
        if var1 == 0:
            return temp, None

        p = 1048576 - adc_P
        p = (((p << 31) - var2) * 3125) // var1
        var1 = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25
        var2 = (self.dig_P8 * p) >> 19
        press = (((p + var1 + var2) >> 8) + (self.dig_P7 << 4)) / 25600.0
        return round(temp, 2), round(press, 2)
