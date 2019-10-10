import sys, serial, os, subprocess
import datetime, time
import numpy as np
import matplotlib.pyplot as plt

############################################################

class IT6D_CA2:
	
	def __init__(self,my_ser):
		
		subprocess.call(['sudo','chown','vfurtula:vfurtula','/dev/ttyUSB0'])
		
		# IT6D_CA2
		self.my_ser=my_ser
		self.ser=serial.Serial(my_ser,baudrate=9600,bytesize=serial.SEVENBITS,parity=serial.PARITY_EVEN,stopbits=serial.STOPBITS_ONE)
		print "IT6D_CA2 microstepper serial port:", my_ser

	def get_positions(self,*argv):
		# interrogate one or both axes
		if len(argv)==1 and argv[0]=='x':
			self.ser.write(''.join(['C1?\n']))
			x_ = self._readline()
			# pick up the right values
			x = x_[4:11]
			# return the values
			return x
		elif len(argv)==1 and argv[0]=='y':
			self.ser.write(''.join(['C2?\n']))
			y_ = self._readline()
			# pick up the right values
			y = y_[4:11]
			# return the values
			return y
		elif len(argv)==0:
			self.ser.write(''.join(['CC?\n']))
			x_and_y = self._readline()
			# pick up the right values
			x = x_and_y[4:11]
			y = x_and_y[16:23]
			# return the values
			return x, y
		else:
			pass
		
	def _readline(self):
		eol=b'\r\n'+chr(47)
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
	
	def __readline(self):
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
  # IT6D_CA2 functions
  ####################################################################
	
	def reset(self,axs):
		#reset the microstepper
		pos=0
		if axs=='x':
			self.ser.write('C1O\n')
		elif axs=='y':
			self.ser.write('C2O\n')
		elif axs=='xy':
			self.ser.write('CCO\n')
		else:
			pass
  
	def move_abs(self,axs,pos_):
		# convert to int if float received
		pos=int(pos_)
		# get axis pointer and read position file
		if axs=='x':
			pointer='1'
		elif axs=='y':
			pointer='2'
		else:
			pass
		# write a position trace to the user
		#print ''.join([axs.capitalize(),'_abs:']),pos
		# move axis
		if pos>0:
			self.ser.write(''.join(['I',pointer,'=+',str(pos),'!\n']))
		elif pos<0:
			self.ser.write(''.join(['I',pointer,'=',str(pos),'!\n']))
		elif pos==0:
			self.ser.write(''.join(['I',pointer,'=-',str(pos),'!\n']))
		else:
			pass
		# wait until the axis has come to rest
		while True:
			self._readline()
			#self.ser.write(''.join(['I',pointer,'?\n']))
			#time.sleep(20e-3)
			if self.__readline()==''.join(['AR',pointer,'\r\n']):
				self.ser.write(''.join(['C',pointer,'?\n']))
				print self._readline()
				return None


	def move_rel(self,axs,pos_):
		# convert to int if float received
		pos=int(pos_)
		# get axis pointer and read position file
		if axs=='x':
			pointer='1'
		elif axs=='y':
			pointer='2'
		else:
			pass
		# calculate absolute position using the relative position
		# get x or y value
		oldpos = self.get_positions(axs)
		newpos=int(oldpos)+pos
		# write a position trace to the user
		#print ''.join([axs,'_rel:']),pos, ''.join([', ',axs.capitalize(),'_abs:']),newpos
		# move and wait until movement finished
		if newpos>0:
			self.ser.write(''.join(['I',pointer,'=+',str(newpos),'!\n']))
		elif newpos<0:
			self.ser.write(''.join(['I',pointer,'=',str(newpos),'!\n']))
		elif newpos==0:
			self.ser.write(''.join(['I',pointer,'=-',str(newpos),'!\n']))
		else:
			pass
		# wait until the axis has come to rest
		while True:
			self._readline()
			#self.ser.write(''.join(['I',pointer,'?\n']))
			#time.sleep(20e-3)
			if self.__readline()==''.join(['AR',pointer,'\r\n']):
				self.ser.write(''.join(['C',pointer,'?\n']))
				print self._readline()
				return None
			

	# clean up serial
	def close(self):
		# flush and close serial
		self.ser.flush()
		self.ser.close()
		print "IT6D_CA2 microstepper serial port flushed and closed" 

def make_test():
	
	move_x=500
	move_y=500
	it6d=IT6D_CA2('/dev/ttyUSB0')
	
	it6d.move_rel('x',move_x)
	it6d.move_rel('y',move_y)
	
	it6d.move_abs('x',1000)
	it6d.move_abs('y',100)

	#it6d.reset('xy')
	it6d.close()


if __name__ == "__main__":
	
	make_test()

  
  
  
