import sys, os, subprocess
import datetime, time
#import Gpib
import numpy as np
import matplotlib.pyplot as plt

############################################################

class IT6D_CA2:
	
	def __init__(self,my_gpb):
		# equal to calls from terminal
		subprocess.call(['sudo','gpib_config'])
		subprocess.call(['sudo','chown','vfurtula:vfurtula','/dev/gpib0'])
		# adr=9 for IT6D_CA2
		self.v=Gpib.Gpib(0,my_gpb)
		print("IT6D_CA2 microstepper GPIB port:", my_gpb)
		
	def get_positions(self,*argv):
		# interrogate one or both axes
		if len(argv)==1 and argv[0]=='x':
			self.v.write(''.join(['C1?\n']).encode())
			x_ = self.v.read().decode()
			# pick up the right values
			x = x_[3:10]
			# return the values
			return x
		elif len(argv)==1 and argv[0]=='y':
			self.v.write(''.join(['C2?\n']).encode())
			y_ = self.v.read().decode()
			# pick up the right values
			y = y_[3:10]
			# return the values
			return y
		elif len(argv)==0:
			self.v.write(''.join(['CC?\n']).encode())
			x_and_y = self.v.read().decode()
			# pick up the right values
			x = x_and_y[3:10]
			y = x_and_y[14:21]
			# return the values
			return x, y
		else:
			pass
		
	def reset(self,axs):
		#reset the microstepper
		if axs=='x':
			self.v.write('C1O\n'.encode())
			time.sleep(15e-3)
		elif axs=='y':
			self.v.write('C2O\n'.encode())
			time.sleep(15e-3)
		elif axs=='xy':
			self.v.write('CCO\n'.encode())
			time.sleep(15e-3)
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
			self.v.write(''.join(['I',pointer,'=+',str(pos),'!\n']).encode())
		elif pos<0:
			self.v.write(''.join(['I',pointer,'=',str(pos),'!\n']).encode())
		elif pos==0:
			self.v.write(''.join(['I',pointer,'=-',str(pos),'!\n']).encode())
		else:
			pass
		# wait until the axis has come to rest
		while True:
			self.v.write(''.join(['I',pointer,'?\n']).encode())
			time.sleep(15e-3)
			if self.v.read().decode()==''.join(['AR',pointer,' ',chr(47)]):
				#self.v.write(''.join(['C',pointer,'?\n']).encode())
				#print self.v.read().decode()
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
			self.v.write(''.join(['I',pointer,'=+',str(newpos),'!\n']).encode())
		elif newpos<0:
			self.v.write(''.join(['I',pointer,'=',str(newpos),'!\n']).encode())
		elif newpos==0:
			self.v.write(''.join(['I',pointer,'=-',str(newpos),'!\n']).encode())
		else:
			pass
		# wait until the axis has come to rest
		while True:
			self.v.write(''.join(['I',pointer,'?\n']).encode())
			time.sleep(15e-3)
			if self.v.read().decode()==''.join(['AR',pointer,' ',chr(47)]):
				#self.v.write(''.join(['C',pointer,'?\n']).encode())
				#print self.v.read().decode()
				return None
		
		
		
def make_test():
	
	move_x=-100
	move_y=-100
	it6d=IT6D_CA2(9)

	it6d.move_rel('x',move_x)
	it6d.move_rel('y',move_y)
	
	it6d.move_abs('x',move_x)
	it6d.move_abs('y',move_y)

	it6d.reset('xy')


if __name__ == "__main__":
	
	make_test()

  
  
  
