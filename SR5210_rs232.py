import sys, subprocess, serial, argparse, time, re
import numpy as np
import matplotlib.pyplot as plt

class SR5210:
	def __init__(self,my_ser):
		
		subprocess.call(['sudo','chown','vfurtula:vfurtula','/dev/ttyS0'])
		# activate the serial. CHECK the serial port name!
		# self.my_ser=12
		self.my_ser=my_ser
		self.ser=serial.Serial(my_ser,baudrate=19200,bytesize=serial.SEVENBITS,parity=serial.PARITY_EVEN,stopbits=serial.STOPBITS_ONE)
		print "SR5210 lock-in serial port:",my_ser
  ############################################################
	# Check input if a number, ie. digits or fractions such as 3.141
	# Source: http://www.pythoncentral.io/how-to-check-if-a-string-is-a-number-in-python-including-unicode/
	def is_number(self,s):
		try:
			float(s)
			return True
		except ValueError:
			pass

		try:
			import unicodedata
			unicodedata.numeric(s)
			return True
		except (TypeError, ValueError):
			pass

		return False
  
  # Pyserial readline() function reads until '\n' is sent (other EOLs are ignored).
  # Therefore changes to readline() are required to match it with EOL character '\r\n'.
  # See: http://stackoverflow.com/questions/16470903/pyserial-2-6-specify-end-of-line-in-readline
	def _readline(self):
		eol=b'\r\n'
		leneol=len(eol)
		line=bytearray()
		while True:
			c=self.ser.read(1)
			if c:
				line+=c
				if line[-leneol:]==eol:
					break
			else:
				break
		return bytes(line)
  
  ####################################################################
  # SR5210 functions
  ####################################################################
	def set_timeout(self,val):
		self.ser.timeout=val
		
	def return_id(self):
		# returns sensitivity
		my_string=''.join(['ID\r'])
		self.ser.write(my_string)
		val=self._readline()
		if isinstance(eval(val), int):
			return int(val)
		else:
			pass
  
	def return_statusByte(self):
		# returns sensitivity
		my_string=''.join(['ST\r'])
		self.ser.write(my_string)
		val=self._readline()
		st_byte='{0:08b}'.format(eval(val))
		return st_byte
		
	def set_as(self):
		# set auto sensitivity
		my_string=''.join(['AS\r'])
		self.ser.write(my_string)
		while True:
			val=self.return_statusByte()
			if val[-1]=='0':
				print "Auto sensitivity is set!"
				return None
			else:
				pass
 
	def return_sen(self):
		# returns sensitivity
		my_string=''.join(['SEN\r'])
		while True:
			self.ser.write(my_string)
			val=self._readline()
			if isinstance(eval(val), int):
				return int(val)
			else:
				pass
		
	def return_X(self):
		# returns X
		my_string=''.join(['X\r'])
		while True:
			self.ser.write(my_string)
			val=self._readline()
			if isinstance(eval(val), int):
				return int(val)
			else:
				pass

	# clean up serial
	def close(self):
		# flush and close serial
		self.ser.flush()
		self.ser.close()
		print "SR5210 lock-in serial port flushed and closed" 


def main():
  
	# call the sr5210 por
	model_5210 = SR5210("/dev/ttyUSB1")
	#model_5210.set_serial()
	
	print model_5210.return_statusByte()
	#model_5210.set_as()
	
	for i in range(100):
		senrangecode=model_5210.return_sen()
		print 'senrangecode =', senrangecode

		# for the equation see page 6-21 in the manual
		senrange=(1+(2*(int(senrangecode)%2)))*10**(int(senrangecode)/2-7)
		print 'senrange =', senrange

		# reads X channel output
		#model_5210.write(''.join(['X']))
		outputuncalib=model_5210.return_X()
		print 'outputuncalib =',outputuncalib

		# assuming N_to_bin[1]=='0' and N_to_bin[2]=='0'
		outputcalib=int(outputuncalib)*senrange*1e-4
		print 'outputcalib =', outputcalib
	
	print model_5210.return_statusByte()
	
	model_5210.close()
	
 
if __name__ == "__main__":
	
  main()
  


