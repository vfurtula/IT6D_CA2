import sys, serial, argparse, time, re, subprocess
import numpy as np
import matplotlib.pyplot as plt 

class SR830:
	
	def __init__(self,my_serial):
		# equal to calls from terminal
		subprocess.call(['sudo','chown','vfurtula:vfurtula','/dev/ttyS0'])
		# activate the serial. CHECK the serial port name!
		self.my_serial=my_serial
		self.ser = serial.Serial(self.my_serial, 19200)
		print "Lock-in serial port:", self.my_serial

	# read from the serial
	def readBytes(self,num):
		data=self.ser.read(num)
		data_ord=[ord(val) for val in data]
		if(len(data_ord)==num): # expected no. of bytes from serial
			pass
			#print "Status byte", bin(data_ord[num-2])[2:]
			#print "Decimal", data_ord[num-1]
		else:
			raise ValueError(''.join(["Exactely ",num," bytes expected from lock-in but got ", str(len(data_ord)),"!"]) )

		return data_ord
  
  ############################################################
	# Check input if a number, ie. digits or fractions such as 3.141
	# Source: http://www.pythoncentral.io/how-to-check-if-a-string-is-a-number-in-python-including-unicode/
	def is_int(self,s):
		try: 
			int(s)
			return True
		except ValueError:
			return False
		
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
  # SR830 functions
  ####################################################################
  
	def set_timeout(self,val):
		self.ser.timeout=val
  
	def set_to_rs232(self):
		my_string=''.join(['OUTX0\r'])
		self.ser.write(my_string)
  
	def set_to_gpib(self):
		my_string=''.join(['OUTX1;FAST1;STRD\r'])
		self.ser.write(my_string)
		
	def set_autoscale(self):
		my_string=''.join(['ASCL\r'])
		self.ser.write(my_string)	
	
	def set_autogain(self):
		my_string=''.join(['AGAN\r'])
		self.ser.write(my_string)

	def return_id(self):
		my_string=''.join(['*IDN?\r'])
		self.ser.write(my_string)
		val=self._readline()
		#print "return_id: ", val
		return val

	def return_reffreq(self):
		while True:
			self.ser.write(''.join(['FREQ?\r']))
			val=self._readline()
			#print "return_reffreq: ", val
			if self.is_number(val):
				return float(val)
	
	def return_snap_data(self):
		# returns values of X, Y, Ref freq
		my_string=''.join(['SNAP?1,2,9\r'])
		self.ser.write(my_string)
		val=self._readline()
		#print "return_snap_data: ", val
		return val
		
	def return_X(self):
		while True:
			self.ser.write(''.join(['OUTP?1\r']))
			val=self._readline()
			#print "return_X: ", val
			if self.is_number(val):
				return float(val)
				
	def return_Y(self):
		while True:
			self.ser.write(''.join(['OUTP?2\r']))
			val=self._readline()
			#print "return_Y: ", val
			if self.is_number(val):
				return float(val)
		
	def return_R(self):
		while True:
			self.ser.write(''.join(['OUTP?3\r']))
			val=self._readline()
			#print "return_R: ", val
			if self.is_number(val):
				return float(val)

	def return_THETA(self):
		while True:
			self.ser.write(''.join(['OUTP?4\r']))
			val=self._readline()
			#print "return_THETA: ", val
			if self.is_number(val):
				return float(val)

	def return_status_bytes(self):
		my_string=''.join(['LIAS?','\r'])
		self.ser.write(my_string)
		val=self._readline()
		val_='{0:08b}'.format(int(val))
		print "return_satus_bytes: ", val_
		return val_
			
	# clean up serial
	def close(self):
		# flush and close serial
		self.ser.flush()
		self.ser.close()
		print "Lock-in port flushed and closed" 

def main():
  
	# call the sr830 por
	sr830 = SR830("/dev/ttyUSB0")
	# do some testing here
	#sr830.set_to_rs232()
	#sr830.set_autoscale()
	
	#sr830.set_autogain()
	'''
	while True:
		val=sr830.return_status_bytes()
		if val[-2]=='1':
			break
	'''
	for ii in range(200):
		sr830.return_X()
		#sr830.return_reffreq()
	
	# clean up and close the sr830 port
	sr830.close()

 
if __name__ == "__main__":
	
  main()
  


