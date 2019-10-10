import sys, serial, argparse, time, re, subprocess
import numpy as np
import matplotlib.pyplot as plt 

class SR810:
	
	def __init__(self,my_serial):
		# equal to calls from terminal
		subprocess.call(['sudo','chown','vfurtula:vfurtula','/dev/ttyS0'])
		# activate the serial. CHECK the serial port name!
		self.ser = serial.Serial(my_serial, 19200)
		print("Lock-in serial port:", my_serial)
		
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
		return bytes(line).decode()
  
  ####################################################################
  # SR810 functions
  ####################################################################
  
	def set_timeout(self,val):
		self.ser.timeout=val
  
	def set_to_rs232(self):
		my_string=''.join(['OUTX0\r'])
		self.ser.write(my_string.encode())
  
	def set_to_gpib(self):
		my_string=''.join(['OUTX1;FAST1;STRD\r'])
		self.ser.write(my_string.encode())
	
	def set_data_sample_rate(self,val):
		if self.is_number(val):
			if val not in range(15):
				raise ValueError("Data sample rate identifier is an integer from 0 to 14!")
			else:
				my_string=''.join(['SRAT',str(val),'\r'])
				self.ser.write(my_string.encode())
		else:
			raise ValueError("Data sample rate identifier is an integer!")
	
	def set_intrl_freq(self,val):
		my_string=''.join(['FMOD1\r'])
		self.ser.write(my_string.encode())
		
		if self.is_number(val):
			my_string=''.join(['FREQ',str(val),'\r'])
			self.ser.write(my_string.encode())
		else:
			raise ValueError("A number is required for the internal frequency!")
	
	def set_intrl_volt(self,val):
		my_string=''.join(['FMOD1\r'])
		self.ser.write(my_string.encode())
		
		if self.is_number(val):
			if val<0.004 or val>0.4:
				raise ValueError("Internal Vpp is at least 4mV and at most 0.4V!")
			else:
				my_string=''.join(['SLVL',str(val),'\r'])
				self.ser.write(my_string.encode())
		else:
			raise ValueError("A number is required for the internal Vpp!")
	
	def set_autoscale(self):
		my_string=''.join(['ASCL\r'])
		self.ser.write(my_string.encode())	
	
	def set_autogain(self):
		my_string=''.join(['AGAN\r'])
		self.ser.write(my_string.encode())

	def return_id(self):
		my_string=''.join(['*IDN?\r'])
		self.ser.write(my_string.encode())
		val=self._readline()
		#print("return_id: ", val)
		return val

	def return_reffreq(self):
		while True:
			self.ser.write(''.join(['FREQ?\r']).encode())
			val=self._readline()
			#print("return_reffreq: ", val)
			if self.is_number(val):
				return float(val)
	
	def return_snap_data(self):
		# returns values of X, Y, Ref freq
		my_string=''.join(['SNAP?1,2,9\r'])
		self.ser.write(my_string.encode())
		val=self._readline()
		#print("return_snap_data: ", val)
		return val
		
	def return_X(self):
		while True:
			self.ser.write(''.join(['OUTP?1\r']).encode())
			val=self._readline()
			#print("return_X: ", val)
			if self.is_number(val):
				return float(val)
				
	def return_Y(self):
		while True:
			self.ser.write(''.join(['OUTP?2\r']).encode())
			val=self._readline()
			#print("return_Y: ", val)
			if self.is_number(val):
				return float(val)
		
	def return_R(self):
		while True:
			self.ser.write(''.join(['OUTP?3\r']).encode())
			val=self._readline()
			#print("return_R: ", val)
			if self.is_number(val):
				return float(val)

	def return_THETA(self):
		while True:
			self.ser.write(''.join(['OUTP?4\r']).encode())
			val=self._readline()
			#print("return_THETA: ", val)
			if self.is_number(val):
				return float(val)

	def return_status_bytes(self):
		my_string=''.join(['LIAS?','\r'])
		self.ser.write(my_string.encode())
		val=self._readline()
		print("return_satus_bytes: ", val)
		return val_
			
	# clean up serial
	def close(self):
		# flush and close serial
		self.ser.flush()
		self.ser.close()
		print("Lock-in port flushed and closed") 

def main():
  
	# call the sr810 por
	sr810 = SR810("/dev/ttyS0")
	# do some testing here
	#sr810.set_to_rs232()
	#sr810.set_autoscale()
	
	#sr810.set_autogain()
	'''
	while True:
		val=sr810.return_status_bytes()
		if val[-2]=='1':
			break
	'''
	for ii in range(200):
		print(sr810.return_X())
		#sr810.return_reffreq()
	
	# clean up and close the sr810 port
	sr810.close()

 
if __name__ == "__main__":
	
  main()
  


