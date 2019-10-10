import sys, serial, argparse, time, re
import numpy as np
import matplotlib.pyplot as plt
import Gpib 

class SR5210:
	def __init__(self,my_gpb):
	  # activate the serial. CHECK the serial port name!
	  # self.my_gpb=12
	  self.my_gpb=my_gpb
	  self.gpb=Gpib.Gpib(0,my_gpb,timeout=12) # 12=3Sec
	  print("SR5210 lock-in GPIB port:",my_gpb)

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
  
  ####################################################################
  # SR5210 functions
  ####################################################################
  
	def set_testechooff(self):
		# set test echo off
		my_string=''.join(['GP ',str(self.my_gpb),' 2'])
		self.gpb.write(my_string)
		while True: 
			val='{0:08b}'.format(ord(self.gpb.serial_poll()))
			if val[-1]=='0':
				print "Test echo off is set!"
				return None
  
	def set_as(self):
		# set auto sensitivity
		my_string=''.join(['AS'])
		self.gpb.write(my_string)
		while True: 
			val='{0:08b}'.format(ord(self.gpb.serial_poll()))
			if val[-1]=='0':
				print "Auto sensitivity is set!"
				return None
 
	def return_sen(self):
		# returns sensitivity
		my_string=''.join(['SEN'])
		self.gpb.write(my_string)
		while True: 
			val='{0:08b}'.format(ord(self.gpb.serial_poll()))
			if val[-1]=='0':
				while True:
					val='{0:08b}'.format(ord(self.gpb.serial_poll()))
					if val[-1]=='0' and val[-8]=='1':
						return self.gpb.read()
		
	def return_X(self):
		# returns X
		my_string=''.join(['X'])
		self.gpb.write(my_string)
		while True: 
			val='{0:08b}'.format(ord(self.gpb.serial_poll()))
			if val[-1]=='0':
				while True:
					val='{0:08b}'.format(ord(self.gpb.serial_poll()))
					if val[-1]=='0' and val[-8]=='1':
						return self.gpb.read()

def main():
  
	# call the sr5210 por
	model_5210 = SR5210(12)
	model_5210.set_testechooff()
	
	#model_5210.set_as()
	
	senrangecode=model_5210.return_sen()
	print 'senrangecode =', senrangecode

	# for the equation see page 6-21 in the manual
	senrange=(1+(2*(int(senrangecode)%2)))*10**(int(senrangecode)/2-7)
	print 'senrange =', senrange

	# reads X channel output
	#model_5210.write(''.join(['X']))
	#time.sleep(self.set_delay)
	outputuncalib=model_5210.return_X()
	print 'outputuncalib =',outputuncalib

	# assuming N_to_bin[1]=='0' and N_to_bin[2]=='0'
	outputcalib=int(outputuncalib)*senrange*1e-4
	print 'outputcalib =', outputcalib
	
 
if __name__ == "__main__":
	
  main()
  


