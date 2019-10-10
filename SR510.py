import sys, serial, argparse, time, re
import numpy as np
import matplotlib.pyplot as plt

class SR510:
	
	def __init__(self,my_serial):
	  # activate the serial. CHECK the serial port name!
	  
	  self.ser=serial.Serial(my_serial,baudrate=19200,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_TWO)
	  print "SR510 serial port:", my_serial
	  time.sleep(1)

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
  # Therefore changes to readline() are required to match it with EOL character '\r'.
  # See: http://stackoverflow.com/questions/16470903/pyserial-2-6-specify-end-of-line-in-readline
	def _readline(self):
		eol=b'\r'
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
  # SR510 functions
  ####################################################################

	def set_timeout(self,val):
		self.ser.timeout=val
	
	def set_local(self):
		my_string=''.join(['I0\r'])
		self.ser.write(my_string)
	
	def set_remote(self):
		my_string=''.join(['I1\r'])
		self.ser.write(my_string)
	
	def set_wait(self,val):
		my_string=''.join(['W',str(val),'\r'])
		self.ser.write(my_string)
	
	def display_voltage(self):
		my_string=''.join(['S0\r'])
		self.ser.write(my_string)
	
	def return_statusbyte(self):
		my_string=''.join(['Y\r'])
		self.ser.write(my_string)
		val=self._readline()
		val_='{0:08b}'.format(int(val))
		print "return_satus_bytes: ", val_
		return val_
	
	def return_wait(self):
		my_string=''.join(['W\r'])
		self.ser.write(my_string)
		val=self._readline()
		if self.is_number(val):
			print "return_wait:",val
			return float(val)
		else:
			print "Bad value returned from lock-in!", val
	
	def return_reffreq(self):
		my_string=''.join(['F\r'])
		self.ser.write(my_string)
		val=self._readline()
		if self.is_number(val):
			#print "return_reffreq: ", val
			return float(val)
		else:
			print "Bad value returned from lock-in!", val
 
	def return_voltage(self):
		# returns voltage
		my_string=''.join(['Q\r'])
		self.ser.write(my_string)
		val=self._readline()
		if self.is_number(val):
			#print "return_voltage:",float(val),"V"
			return float(val)
		else:
			print "Bad value returned from lock-in!", val
	
	# clean up serial
	def close(self):
		# flush and close serial
		self.ser.flush()
		self.ser.close()
		print "SR510 port flushed and closed" 
				
def main():
  
	# call the sr510 port
	model_510 = SR510("COM23")
	
	model_510.set_remote()
	model_510.display_voltage()
	model_510.return_wait()
	model_510.set_wait(1)
	model_510.return_statusbyte()
	for i in range(10):
		model_510.return_voltage()
	
	# clean up and close the sr510 port
	model_510.close()
	
if __name__ == "__main__":
	
  main()
  


