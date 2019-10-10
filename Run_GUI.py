#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Fri FEB 16 09:06:01 2018

@author: Vedran Furtula
"""

import traceback, os, sys, re, serial, time, numpy, yagmail, sqlite3, configparser, getpass

import matplotlib as mpl
from matplotlib import cm
import numpy.polynomial.polynomial as poly
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

import scipy.io as io
import scipy.optimize as scop
from scipy.interpolate import UnivariateSpline

from PyQt5.QtCore import QObject, QThreadPool, QTimer, QRunnable, pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QDialog, QWidget, QMainWindow, QSlider, QLCDNumber, QMessageBox, QGridLayout, QCheckBox,
														 QInputDialog, QLabel, QLineEdit, QComboBox, QFrame, QTableWidget, QTableWidgetItem,
														 QVBoxLayout, QHBoxLayout, QApplication, QMenuBar, QPushButton, QFileDialog)

import pyqtgraph as pg
import pyqtgraph.exporters

import SR810, Methods_for_IT6D_CA2, Send_email_dialog, Email_settings_dialog, Write2file_dialog, Load_config_dialog
import IT6D_CA2_gpib
from help_dialogs import Indicator_dialog, Message_dialog
import asyncio









class WorkerSignals(QObject):
	# Create signals to be used
	Spath = pyqtSignal(object)
	lcd = pyqtSignal(object)
	pos_lcd = pyqtSignal(object)
	color_map = pyqtSignal(object)
	plot_gaussian = pyqtSignal(object)
	Umax = pyqtSignal(object)
	
	slope = pyqtSignal(object)
	fwhm_1D = pyqtSignal(object)
	fwhm_2D = pyqtSignal(object)
	make_3Dplot = pyqtSignal()
	warning = pyqtSignal(object)
	
	update2 = pyqtSignal(object)
	update4 = pyqtSignal(object)
	
	error = pyqtSignal(object)
	finished = pyqtSignal()
	
	
	


class Email_Worker(QRunnable):
	'''
	Worker thread
	:param args: Arguments to make available to the run code
	:param kwargs: Keywords arguments to make available to the run code
	'''
	def __init__(self,*argv):
		super(Email_Worker, self).__init__()
		
		# constants	
		self.subject = argv[0].subject
		self.contents = argv[0].contents
		self.emailset_str = argv[0].settings
		self.emailrec_str = argv[0].receivers
		
		self.signals = WorkerSignals()
		
		
	@pyqtSlot()
	def run(self):
		'''
		Initialise the runner function with passed args, kwargs.
		'''
		# Retrieve args/kwargs here; and fire processing using them
		try:
			self.yag = yagmail.SMTP(self.emailset_str[0], getpass.getpass( prompt=''.join(["Password for ",self.emailset_str[0],"@gmail.com:"]) ))
			self.yag.send(to=self.emailrec_str, subject=self.subject, contents=self.contents)
			self.signals.warning.emit(''.join(["E-mail is sent to ", ' and '.join([i for i in self.emailrec_str]) ," including ",str(len(self.contents[1:]))," attachment(s)!"]))
		except Exception as e:
			self.signals.critical.emit(''.join(["Could not send e-mail from the gmail account ",self.emailset_str[0],"! Try following steps:\n1. Check your internet connection. \n2. Check the account username and password.\n3. Make sure that the account accepts less secure apps.\n4. Make sure that keyring.get_password(\"system\", \"username\") works in your operating system.\n\n",str(e)]))
		else:
			pass
		finally:
			self.signals.finished.emit()
	
	
	
	
class IT6D_CA2_Worker(QRunnable):
	'''
	Worker thread
	:param args: Arguments to make available to the run code
	:param kwargs: Keywords arguments to make available to the run code
	'''
	def __init__(self,*argv):
		super(IT6D_CA2_Worker, self).__init__()
		
		# constants	
		self.arg = argv[0]
		self.op_mode = self.arg.op_mode
		self.it6d = self.arg.it6d
		
		self.abort_flag = False
		self.signals = WorkerSignals()
		
		
	@pyqtSlot()
	def run(self):
		'''
		Initialise the runner function with passed args, kwargs.
		'''
		# Retrieve args/kwargs here; and fire processing using them
		if self.op_mode=='xyscan':
			self.xscan = self.arg.xscan
			self.yscan = self.arg.yscan
			self.smartscan_check = self.arg.smart_scan
			self.scan_mode = self.arg.scan_mode
			self.dwell_time = self.arg.dwell_time
			self.sr810 = self.arg.sr810
			self.xyscan()
		
		elif self.op_mode=='xscan':
			self.xscan = self.arg.xscan
			self.dwell_time = self.arg.dwell_time
			self.sr810 = self.arg.sr810
			self.def_xscan()
		
		elif self.op_mode=='yscan':
			self.yscan = self.arg.yscan
			self.dwell_time = self.arg.dwell_time
			self.sr810 = self.arg.sr810
			self.def_yscan()
		
		elif self.op_mode=='move rel':
			self.xscan = self.arg.xscan
			self.yscan = self.arg.yscan
			self.move_rel()
		
		elif self.op_mode=='move abs':
			self.xscan = self.arg.xscan
			self.yscan = self.arg.yscan
			self.move_abs()
		
		elif self.op_mode=='reset':
			self.reset_mode = self.arg.reset_mode
			self.reset()
			
		self.signals.finished.emit()  # Done
		
		
	def abort(self):
		
		self.abort_flag=True
	
	
	def nearest_point(self,a,b,c,x1,y1):
		# Nearest point on line ax+by+c=0 to the point (x1,y1)
		x=(b*(b*x1-a*y1)-a*c)/(a**2+b**2)
		y=(a*(-b*x1+a*y1)-b*c)/(a**2+b**2)	
		return x,y
	
	
	def dist_to_line(self,p0,x1,y1):
		# Shortest distance between line ax+by+c=0 and points (x1,y1)
		return (p0[0]*x1+p0[1]*y1+p0[2])/(p0[0]**2+p0[1]**2)**0.5
	
	
	def gauss(self,x,p): 
		#p[0]==mean, p[1]==stdev, p[2]==peak height, p[3]==noise floor
		return p[2]*numpy.exp(-(x-p[0])**2/(2*p[1]**2))+p[3]
	
	
	def fit_to_gauss(self,pos,volts):
		# Fit a gaussian
		# p0 is the initial guess for the gaussian
		p0 = [pos[numpy.argmax(volts)]] # mean
		p0.extend([numpy.std(volts)]) # stdev
		p0.extend([max(volts)-min(volts)]) # peak height
		p0.extend([min(volts)]) # noise floor
		
		errfunc = lambda p,x,y: self.gauss(x,p)-y # Distance to the target function
		try:
			p1, success = scop.leastsq(errfunc, p0, args=(pos,volts))
		except Exception as e:
			self.signals.warning.emit(str(e))
		
		#fit_stdev = p1[1]
		#fwhm_2D = 2*(2*numpy.log(2))**0.5*fit_stdev
		sorted_pos=numpy.argsort(pos)
		spl=UnivariateSpline(pos[sorted_pos],volts[sorted_pos]-numpy.max(volts)/2,s=0)
		try:
			r1,r2 = spl.roots()
		except Exception as e:
			self.signals.warning.emit(str(e))
			r1,r2=[0,0]
		
		return p1,r1,r2
	
	
	def atten(self,S,p):
		
		return p[1]*numpy.exp(-S*p[0])
	
	
	def fit_to_atten(self,S,volts):
		# Fit a gaussian
		p0 = [1,1] # Initial guess for the gaussian
		errfunc = lambda p,x,y: self.atten(x,p)-y # Distance to the target function
		try:
			p1, success = scop.leastsq(errfunc, p0[:], args=(S,numpy.array(volts)))
		except Exception as e:
			self.signals.warning.emit(str(e))
		#a, b = p1
		return p1
		
		
	def update_graphs(self,save_x,save_y,save_Umax,tal):
		
		self.signals.Umax.emit([save_x,save_y])

		if tal==0:
			S=numpy.array([0])
			return S
			
		elif tal==1:
			S=numpy.array([0])
			S=numpy.append(S, (numpy.diff(save_x)**2+numpy.diff(save_y)**2)**0.5)
			return S
		
		elif tal>1:
			save_Umax = numpy.array(save_Umax)
			# Shortest distance between line ax+by+c=0 and point (x1,y1)
			p0 = [1,1,1] # Initial guess for the gaussian
			errfunc = lambda p,xp,yp: self.dist_to_line(p,xp,yp) # Distance to the target function
			try:
				p1, success = scop.leastsq(errfunc, p0[:], args=(numpy.array(save_x),numpy.array(save_y)))
				a,b,c = p1
			except Exception as e:
				self.signals.warning.emit(str(e))

			xp_acc,yp_acc = self.nearest_point(a,b,c,numpy.array(save_x),numpy.array(save_y))

			delta_xy=(numpy.diff(xp_acc)**2+numpy.diff(yp_acc)**2)**0.5
			S=numpy.array([0])
			S=numpy.append(S, numpy.add.accumulate(delta_xy))
			xp_sor_round = numpy.round(xp_acc,6) # 1 um round accuracy
			yp_sor_round = numpy.round(yp_acc,7) # 0.1 um round accuracy
			
			self.signals.Spath.emit([xp_sor_round,yp_sor_round,S,save_Umax])
		
			return S
		
		
	def update_graphs1(self,save_x,save_y):
		
		self.signals.Umax.emit([save_x,save_y])
		
		
	def xyscan(self):
		
		save_x=[]
		save_y=[]
		save_Umax=[]
		a2=[]
		fwhm_1D=[]
		fwhm_2D=[]
		tals=[]
		i_,j_ = self.it6d.get_positions()
		
		x_array=self.xscan
		y_array=self.yscan
		
	  ###########################################
		
		if self.scan_mode=='xwise':
			
			time_start=time.time()
			for j,tal_outer in zip(y_array,range(len(y_array))):
				self.it6d.move_abs('y',j)
				j_ = self.it6d.get_positions('y')
				self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
				voltages=[]
				pos_x=[]
				for i in x_array:
					if self.abort_flag:
						return
					# move the microsteppers to the calculated positions
					self.it6d.move_abs('x',i)
					i_ = self.it6d.get_positions('x')
					self.signals.pos_lcd.emit([1e-6*int(i_),1e-7*int(j_)])
					time_now=time.time()
					# update voltage readouts during dwell time
					while (time.time()-time_now)<self.dwell_time and not self.abort_flag:
						voltage=self.sr810.return_X()
						time_elap=time.time()-time_start
						self.signals.update2.emit([time_elap,1e-6*int(i_),voltage])
					self.signals.color_map.emit(voltage)
					self.signals.update4.emit([1e-6*int(i_),1e-7*int(j_),voltage,time_elap])
					print('X_abs:',int(i_), ', Y_abs:',int(j_), ', Vlockin:',voltage)
					# calculate spine positions along the x axis
					pos_x.extend([ numpy.round(1e-6*int(i_),6) ])
					voltages.extend([ voltage ])
				
				if self.abort_flag:
					return
				ind_max=numpy.argmax(voltages)
				
				save_x.extend([ pos_x[ind_max] ])
				save_y.extend([ numpy.round(1e-7*int(j_),7) ])
				save_Umax.extend([ voltages[ind_max] ])
				
				S = self.update_graphs(save_x,save_y,save_Umax,tal_outer)
				p1,r1,r2 = self.fit_to_gauss(numpy.array(pos_x),numpy.array(voltages))
				
				tals.extend([ tal_outer ])
				fwhm_2D.extend([ abs(r1-r2) ])
				
				self.signals.fwhm_2D.emit([tals,S,save_x,save_y,save_Umax,fwhm_2D])
				print("FWHM:", abs(r1-r2), "m")
				
				gauss_pos = numpy.linspace(min(pos_x),max(pos_x),5*len(pos_x))
				gauss_volts = self.gauss(gauss_pos,p1)
				self.signals.plot_gaussian.emit([pos_x,voltages,'y',save_y[-1],gauss_pos,gauss_volts,[r1,r2]])
				
				if len(tals)>1:
					coef = self.fit_to_atten(S,save_Umax)
					a2.extend([ 4.343*coef[0]/100 ])
					self.signals.slope.emit([tals[1:],a2])
				
				if self.smartscan_check:
					x_array=x_array+(ind_max-len(x_array)/2)*(x_array[1]-x_array[0])
				
		elif self.scan_mode=='ywise':

			time_start=time.time()
			for i,tal_outer in zip(x_array,range(len(x_array))):
				self.it6d.move_abs('x',i)
				i_ = self.it6d.get_positions('x')
				self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
				voltages=[]
				pos_y=[]
				for j in y_array:
					if self.abort_flag:
						return
					# move the miself.it6dcrosteppers to the calculated positions
					self.it6d.move_abs('y',j)
					j_ = self.it6d.get_positions('y')
					self.signals.pos_lcd.emit([1e-6*int(i_),1e-7*int(j_)])
					time_now=time.time()
					# update voltage readouts during dwell time
					while (time.time()-time_now)<self.dwell_time and not self.abort_flag:
						voltage=self.sr810.return_X()
						time_elap=time.time()-time_start
						self.signals.update2.emit([time_elap,1e-7*int(j_),voltage])
					self.signals.color_map.emit(voltage)
					self.signals.update4.emit([1e-6*int(i_),1e-7*int(j_),voltage,time_elap])
					print('X_abs:',int(i_), ', Y_abs:',int(j_), ', Vlockin:',voltage)
					# calculate spine positions along the y axis
					pos_y.extend([ numpy.round(1e-7*int(j_),7) ])
					voltages.extend([ voltage ])
			
				if self.abort_flag:
					return
				ind_max=numpy.argmax(voltages)
				
				save_x.extend([ numpy.round(1e-6*int(i_),6) ])
				save_y.extend([ pos_y[ind_max] ])
				save_Umax.extend([ voltages[ind_max] ])
				
				S = self.update_graphs(save_x,save_y,save_Umax,tal_outer)
				p1,r1,r2 = self.fit_to_gauss(numpy.array(pos_y),numpy.array(voltages))
				
				tals.extend([ tal_outer ])
				fwhm_2D.extend([ abs(r1-r2) ])
				
				self.signals.fwhm_2D.emit([tals,S,save_x,save_y,save_Umax,fwhm_2D])
				print("FWHM:", abs(r1-r2), "m")
				
				gauss_pos = numpy.linspace(min(pos_y),max(pos_y),5*len(pos_y))
				gauss_volts = self.gauss(gauss_pos,p1)
				self.signals.plot_gaussian.emit([pos_y,voltages,'x',save_x[-1],gauss_pos,gauss_volts,[r1,r2]])
				
				if len(tals)>1:
					coef = self.fit_to_atten(S,save_Umax)
					a2.extend([ 4.343*coef[0]/100 ])
					self.signals.slope.emit([tals[1:],a2])
				
				if self.smartscan_check:
					y_array=y_array+(ind_max-len(y_array)/2)*(y_array[1]-y_array[0])
					
		elif self.scan_mode=='xsnake':
			
			turn=-1
			time_start=time.time()
			for j,tal_outer in zip(y_array,range(len(y_array))):
				self.it6d.move_abs('y',j)
				j_ = self.it6d.get_positions('y')
				self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
				turn=turn*-1
				voltages=[]
				pos_x=[]
				for i in x_array[::turn]:
					if self.abort_flag:
						return
					# move the microsteppers to the calculated positions
					self.it6d.move_abs('x',i)
					i_ = self.it6d.get_positions('x')
					self.signals.pos_lcd.emit([1e-6*int(i_),1e-7*int(j_)])
					time_now=time.time()
					# update voltage readouts during dwell time
					while (time.time()-time_now)<self.dwell_time and not self.abort_flag:
						voltage=self.sr810.return_X()
						time_elap=time.time()-time_start
						self.signals.update2.emit([time_elap,1e-6*int(i_),voltage])
					self.signals.color_map.emit(voltage)
					self.signals.update4.emit([1e-6*int(i_),1e-7*int(j_),voltage,time_elap])
					print('X_abs:',int(i_), ', Y_abs:',int(j_), ', Vlockin:',voltage)
					# calculate spine positions along the x axis
					pos_x.extend([ numpy.round(1e-6*int(i_),6) ])
					voltages.extend([ voltage ])
				
				if self.abort_flag:
					return
				ind_max=numpy.argmax(voltages)
				
				save_x.extend([ pos_x[ind_max] ])
				save_y.extend([ numpy.round(1e-7*int(j_),7) ])
				save_Umax.extend([ voltages[ind_max] ])
				
				S = self.update_graphs(save_x,save_y,save_Umax,tal_outer)
				p1,r1,r2 = self.fit_to_gauss(numpy.array(pos_x),numpy.array(voltages))
				
				tals.extend([ tal_outer ])
				fwhm_2D.extend([ abs(r1-r2) ])
				
				self.signals.fwhm_2D.emit([tals,S,save_x,save_y,save_Umax,fwhm_2D])
				print("FWHM:", abs(r1-r2), "m")
				
				gauss_pos = numpy.linspace(min(pos_x),max(pos_x),5*len(pos_x))
				gauss_volts = self.gauss(gauss_pos,p1)
				self.signals.plot_gaussian.emit([pos_x,voltages,'y',save_y[-1],gauss_pos,gauss_volts,[r1,r2]])
				
				if len(tals)>1:
					coef = self.fit_to_atten(S,save_Umax)
					a2.extend([ 4.343*coef[0]/100 ])
					self.signals.slope.emit([tals[1:],a2])
				
				if self.smartscan_check:
					x_array=x_array+(ind_max-len(x_array)/2)*(x_array[1]-x_array[0])*turn
					
		elif self.scan_mode=='ysnake':
			
			turn=-1
			time_start=time.time()
			for i,tal_outer in zip(x_array,range(len(x_array))):
				self.it6d.move_abs('x',i)
				i_ = self.it6d.get_positions('x')
				self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
				turn=turn*-1
				voltages=[]
				pos_y=[]
				for j in y_array[::turn]:
					if self.abort_flag:
						return
					# move the microsteppers to the calculated positions
					self.it6d.move_abs('y',j)
					j_ = self.it6d.get_positions('y')
					self.signals.pos_lcd.emit([1e-6*int(i_),1e-7*int(j_)])
					time_now=time.time()
					# update voltage readouts during dwell time
					while (time.time()-time_now)<self.dwell_time and not self.abort_flag:
						voltage=self.sr810.return_X()
						time_elap=time.time()-time_start
						self.signals.update2.emit([time_elap,1e-7*int(j_),voltage])
					self.signals.color_map.emit(voltage)
					self.signals.update4.emit([1e-6*int(i_),1e-7*int(j_),voltage,time_elap])
					print('X_abs:',int(i_),', Y_abs:',int(j_),', Vlockin:',voltage)
					# calculate spine positions along the y axis
					pos_y.extend([ numpy.round(1e-7*int(j_),7) ])
					voltages.extend([ voltage ])
				
				if self.abort_flag:
					return
				ind_max=numpy.argmax(voltages)
				
				save_x.extend([ numpy.round(1e-6*int(i_),6) ])
				save_y.extend([ pos_y[ind_max] ])
				save_Umax.extend([ voltages[ind_max] ])
					
				S = self.update_graphs(save_x,save_y,save_Umax,tal_outer)
				p1,r1,r2 = self.fit_to_gauss(numpy.array(pos_y),numpy.array(voltages))
				
				tals.extend([ tal_outer ])
				fwhm_2D.extend([ abs(r1-r2) ])
				
				self.signals.fwhm_2D.emit([tals,S,save_x,save_y,save_Umax,fwhm_2D])
				print("FWHM:", abs(r1-r2), "m")
				
				gauss_pos = numpy.linspace(min(pos_y),max(pos_y),5*len(pos_y))
				gauss_volts = self.gauss(gauss_pos,p1)
				self.signals.plot_gaussian.emit([pos_y,voltages,'x',save_x[-1],gauss_pos,gauss_volts,[r1,r2]])
				
				if len(tals)>1:
					coef = self.fit_to_atten(S,save_Umax)
					a2.extend([ 4.343*coef[0]/100 ])
					self.signals.slope.emit([tals[1:],a2])
				
				if self.smartscan_check:
					y_array=y_array+(ind_max-len(y_array)/2)*(y_array[1]-y_array[0])*turn
					
		else:
			pass
		
		if tal_outer>1:
			# plot the data as a contour plot
			time.sleep(1)
			self.signals.make_3Dplot.emit()
			
			
	def def_xscan(self):
		
		j_ = self.it6d.get_positions('y')
			
		time_start=time.time() 
		voltages=[]
		pos_x=[]
		for i in self.xscan:
			if self.abort_flag:
				return
			self.it6d.move_abs('x',i)
			i_ = self.it6d.get_positions('x')
			self.signals.pos_lcd.emit([1e-6*int(i_),1e-7*int(j_)])
			time_now=time.time()
			# update voltage readouts during dwell time
			while (time.time()-time_now)<self.dwell_time and not self.abort_flag:
				voltage=self.sr810.return_X()
				time_elap=time.time()-time_start
				self.signals.update2.emit([time_elap,1e-6*int(i_),voltage])
			self.signals.color_map.emit(voltage)
			self.signals.update4.emit([1e-6*int(i_),1e-7*int(j_),voltage,time_elap])
			#self.emit(SIGNAL('make_update3(PyQt_PyObject,PyQt_PyObject)'),time_elap,1e-6*int(i_))
			print('X_abs:',int(i_),', Y_abs:',int(j_),', Vlockin:',voltage)
			pos_x.extend([ numpy.round(1e-6*int(i_),6) ])
			voltages.extend([ voltage ])
			
		ind_max=numpy.argmax(voltages)
		
		self.update_graphs1([pos_x[ind_max]], [numpy.round(1e-7*int(j_),7)])
		p1,r1,r2 = self.fit_to_gauss(numpy.array(pos_x),numpy.array(voltages))
		
		self.signals.fwhm_1D.emit([[0],[abs(r1-r2)]])
		print("FWHM:", abs(r1-r2), "m")
		
		gauss_pos = numpy.linspace(min(pos_x),max(pos_x),5*len(pos_x))
		gauss_volts = self.gauss(gauss_pos,p1)
		self.signals.plot_gaussian.emit([pos_x,voltages,'y',1e-7*int(j_),gauss_pos,gauss_volts,[r1,r2]])
		
		
	def def_yscan(self):
		
		i_ = self.it6d.get_positions('x')

		time_start=time.time()
		voltages=[]
		pos_y=[]
		for j in self.yscan:
			if self.abort_flag:
				return
			self.it6d.move_abs('y',j)
			j_ = self.it6d.get_positions('y')
			self.signals.pos_lcd.emit([1e-6*int(i_),1e-7*int(j_)])
			time_now=time.time()
			# update voltage readouts during dwell time
			while (time.time()-time_now)<self.dwell_time and not self.abort_flag:
				voltage=self.sr810.return_X()
				time_elap=time.time()-time_start
				self.signals.update2.emit([time_elap,1e-7*int(j_),voltage])
			self.signals.color_map.emit(voltage)
			self.signals.update4.emit([1e-6*int(i_),1e-7*int(j_),voltage,time_elap])
			#self.emit(SIGNAL('make_update3(PyQt_PyObject,PyQt_PyObject)'),time_elap,1e-7*int(j_))
			print('X_abs:',int(i_),', Y_abs:',int(j_),', Vlockin:',voltage)
			pos_y.extend([ numpy.round(1e-7*int(j_),7) ])
			voltages.extend([ voltage ])
			
		ind_max=numpy.argmax(voltages)
		
		self.update_graphs1([numpy.round(1e-6*int(i_),6)], [pos_y[ind_max]])
		p1,r1,r2 = self.fit_to_gauss(numpy.array(pos_y),numpy.array(voltages))
		
		self.signals.fwhm_1D.emit([[0],[abs(r1-r2)]])
		print("FWHM:", abs(r1-r2), "m")
		
		gauss_pos = numpy.linspace(min(pos_y),max(pos_y),5*len(pos_y))
		gauss_volts = self.gauss(gauss_pos,p1)
		self.signals.plot_gaussian.emit([pos_y,voltages,'x',1e-6*int(i_),gauss_pos,gauss_volts,[r1,r2]])
		
		
	def move_rel(self):
		
		if not self.abort_flag:
			self.it6d.move_rel('x',self.xscan)
			i_,j_ = self.it6d.get_positions()
			self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
			
		if not self.abort_flag:
			self.it6d.move_rel('y',self.yscan)
			i_,j_ = self.it6d.get_positions()
			self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
			
			
	def move_abs(self):
		
		if not self.abort_flag:
			self.it6d.move_abs('x',self.xscan)
			i_,j_ = self.it6d.get_positions()
			self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
			
		if not self.abort_flag:
			self.it6d.move_abs('y',self.yscan)
			i_,j_ = self.it6d.get_positions()
			self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
			
			
	def reset(self):
		
		self.it6d.reset(self.reset_mode)
		i_,j_ = self.it6d.get_positions()
		self.signals.lcd.emit([1e-6*int(i_),1e-7*int(j_)])
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
class Run_IT6D_CA2(QMainWindow):

	def __init__(self):
		super().__init__()
		
		self.cwd = os.getcwd()
		self.load_()
		
		# Enable antialiasing for prettier plots		
		pg.setConfigOptions(antialias=True)
		self.initUI()
			
	def initUI(self):
		
		################### MENU BARS START ##################
		
		MyBar = QMenuBar(self)
		fileMenu = MyBar.addMenu("File")
		self.fileLoadAs = fileMenu.addAction("Config section settings")        
		self.fileLoadAs.triggered.connect(self.load_config_dialog)
		self.write2file = fileMenu.addAction("Write to file")
		self.write2file.triggered.connect(self.write2fileDialog)
		fileSavePlt = fileMenu.addAction("Save plots")
		fileSavePlt.triggered.connect(self.save_plots)
		fileSavePlt.setShortcut('Ctrl+P')
		fileSaveSet = fileMenu.addAction("Save settings")        
		fileSaveSet.triggered.connect(self.save_) # triggers closeEvent()
		fileSaveSet.setShortcut('Ctrl+S')
		self.fileClose = fileMenu.addAction("Close")        
		self.fileClose.triggered.connect(self.close) # triggers closeEvent()
		self.fileClose.setShortcut('Ctrl+X')
		
		modeMenu = MyBar.addMenu("Mode")
		self.conMode = modeMenu.addAction("Connect to serial")
		self.conMode.triggered.connect(self.set_connect)
		self.disconMode = modeMenu.addAction("Disconnect from serial")
		self.disconMode.triggered.connect(self.set_disconnect)
		
		gpibMenu = MyBar.addMenu("Ports")
		self.gpibIT6D_CA2 = gpibMenu.addAction("IT6D CA2")
		self.gpibIT6D_CA2.triggered.connect(self.IT6D_CA2Dialog)
		self.serSR810 = gpibMenu.addAction("SR810")
		self.serSR810.triggered.connect(self.SR810Dialog)
		
		self.emailMenu = MyBar.addMenu("E-mail")
		self.emailSet = self.emailMenu.addAction("E-mail settings")
		self.emailSet.triggered.connect(self.email_set_dialog)
		self.emailData = self.emailMenu.addAction("E-mail data")
		self.emailData.triggered.connect(self.email_data_dialog)
		
		################### MENU BARS END ##################
		
		lbl1 = QLabel("OPERATION mode settings:", self)
		lbl1.setStyleSheet("color: blue")	
		
		opmode_lbl = QLabel("Operation", self)
		self.combo4 = QComboBox(self)
		self.mylist4=["move abs","move rel","xyscan","xscan","yscan","reset"]
		self.combo4.addItems(self.mylist4)
		self.combo4.setCurrentIndex(self.mylist4.index(self.op_mode))
		
		scanmode_lbl = QLabel("Scan", self)
		self.combo5 = QComboBox(self)
		self.mylist5=["xsnake","ysnake","xwise","ywise"]
		self.combo5.addItems(self.mylist5)
		self.combo5.setCurrentIndex(self.mylist5.index(self.scan_mode))
		
		resetmode_lbl = QLabel("Reset", self)
		self.combo6 = QComboBox(self)
		self.mylist6=["x","y","xy"]
		self.combo6.addItems(self.mylist6)
		self.combo6.setCurrentIndex(self.mylist6.index(self.reset_mode))
		
		dwelltime_lbl = QLabel("Dwell [s]",self)
		self.dwelltimeEdit = QLineEdit(self.dwell_time,self)
		xy_limiter_lbl = QLabel("XY-limits [mm]",self)
		self.xy_limiterEdit = [QLineEdit("",self) for tal in range(2)]
		for i in range(2):
			self.xy_limiterEdit[i].setText(self.xy_limiter_mm[i])
			self.xy_limiterEdit[i].setFixedWidth(50)
		
		smartscan_lbl=QLabel("Smart scan",self)
		self.cb_smartscan = QCheckBox('',self)
		self.cb_smartscan.toggle()
		self.cb_smartscan.setChecked(self.smartscan_check)
		
		#####################################################
			
		#lockin_lbl = QLabel("SR810 lock-in oscillator settings:", self)
		#lockin_lbl.setStyleSheet("color: blue")	
		
		self.amp_lbl = QLabel(''.join(["Osc. Vpk-pk (",str(self.lockin_volt),") [V]"]), self)
		self.sld_amp = QSlider(Qt.Horizontal,self)
		#self.sld_amp.setFocusPolicy(Qt.NoFocus)
		self.sld_amp.tickPosition()
		self.sld_amp.setRange(1,400)
		self.sld_amp.setSingleStep(1)
		self.sld_amp.setPageStep(10)
		self.sld_amp.setValue(int(1000*self.lockin_volt))
		
		self.freq_lbl = QLabel(''.join(["Osc. freq (",str(self.lockin_freq),") [Hz]"]), self)
		self.sld_freq = QSlider(Qt.Horizontal,self)
		#self.sld_freq.setFocusPolicy(Qt.NoFocus)
		self.sld_freq.tickPosition()
		self.sld_freq.setRange(1,5000)
		self.sld_freq.setSingleStep(1)
		self.sld_freq.setPageStep(10)
		self.sld_freq.setValue(self.lockin_freq)
		
		#self.freqEdit=QLineEdit("",self)
		#self.freqEdit.setText(str(self.lockin_freq))
		#self.freqEdit.setFixedWidth(60)
		#self.freqEdit.setEnabled(False)
		
		#rate_lbl = QLabel("Sample rate[Hz]", self)
		#self.combo8 = QComboBox(self)
		#self.mylist8=["0.0625","0.125","0.25","0.5","1.0","2.0","4.0","8.0","16.0","32.0","64.0","128.0","256.0","512.0"]
		#self.combo8.addItems(self.mylist8)
		#self.combo8.setCurrentIndex(self.mylist8.index(str(self.sample_rate)))
			
		#####################################################
		
		lbl7 = QLabel("SCAN or MOVE axis[mm]:", self)
		lbl7.setStyleSheet("color: blue")	
		
		start_lbl = QLabel("Start",self)
		stop_lbl = QLabel("Stop",self)
		step_lbl = QLabel("Step",self)
		self.absrel_lbl = QLabel("Abs/Rel",self)
		xy_lbl = [QLabel(i,self) for i in ["X:","Y:"]]
		[xy_lbl[i].setFixedWidth(15) for i in range(2)]
		self.xscanEdit = [QLineEdit("",self) for tal in range(3)] 
		self.yscanEdit = [QLineEdit("",self) for tal in range(3)]
		self.absrelEdit = [QLineEdit("",self) for tal in range(2)]
		# set initial values into the fields
		for i in range(3):
			self.xscanEdit[i].setText(self.xscan[i])
			self.yscanEdit[i].setText(self.yscan[i])
			self.xscanEdit[i].setFixedWidth(53)
			self.yscanEdit[i].setFixedWidth(53)
		for i in range(2):
			self.absrelEdit[i].setText(self.absrel_mm[i])
			self.absrelEdit[i].setFixedWidth(50)
			
		actual_lbl = QLabel("Actual",self)
		self.lcd_actual = [QLCDNumber(self) for i in range(2)]
		for i in range(2):
			self.lcd_actual[i].setStyleSheet("color: blue")
			#self.lcd_actual.setFixedHeight(60)
			self.lcd_actual[i].setSegmentStyle(QLCDNumber.Flat)
			self.lcd_actual[i].setNumDigits(7)
			self.lcd_actual[i].display('-------')
		
		#####################################################
		
		schroll_lbl = QLabel("Schroll X-axis",self)
		self.combo2 = QComboBox(self)
		self.mylist2=["200","500","1000","2000","5000","10000"]
		self.combo2.addItems(self.mylist2)
		# initial combo settings
		self.combo2.setCurrentIndex(self.mylist2.index(str(self.schroll_pts)))
		#self.combo2.setFixedWidth(90)
		
		#####################################################
		
		lbl5 = QLabel("EXECUTE operation:", self)
		lbl5.setStyleSheet("color: blue")
		
		self.runButton = QPushButton("Run",self)
		self.cancelButton = QPushButton("STOP",self)
		
		#####################################################
		
		lbl4 = QLabel("Write to file(s):", self)
		lbl4.setStyleSheet("color: blue")
		txtfile_lbl = QLabel("Text file:",self)
		dbfile_lbl = QLabel("SQL database file:",self)
		matfile_lbl = QLabel("Matlab file:",self)
		self.txtfile_ = QLabel("",self)
		self.dbfile_ = QLabel("",self)
		self.matfile_ = QLabel("",self)
		if self.write2txt_check:
			self.txtfile_.setText(''.join([self.write2txt_str,' (.txt)']))
			self.txtfile_.setStyleSheet("color: green")
		else:
			self.txtfile_.setText("No text file")
			self.txtfile_.setStyleSheet("color: red")
			
		if self.write2db_check:
			self.dbfile_.setText(''.join([self.write2db_str,' (.db)']))
			self.dbfile_.setStyleSheet("color: green")
		else:
			self.dbfile_.setText("No database file")
			self.dbfile_.setStyleSheet("color: red")
		
		if self.write2mat_check:
			self.matfile_.setText(''.join([self.write2mat_str,' (.mat)']))
			self.matfile_.setStyleSheet("color: green")
		else:
			self.matfile_.setText("No matlab file")
			self.matfile_.setStyleSheet("color: red")
		
		#####################################################
		
		self.lcd_time = QLCDNumber(self)
		self.lcd_time.setStyleSheet("color: red")
		self.lcd_time.setFixedHeight(60)
		self.lcd_time.setSegmentStyle(QLCDNumber.Flat)
		self.lcd_time.setNumDigits(11)
		self.lcd_time.display(self.timestr)
			
		#####################################################
		
		# Add all widgets		
		g1_0 = QGridLayout()
		g1_0.addWidget(MyBar,0,0)
		g1_0.addWidget(lbl1,1,0)

		g1_1 = QGridLayout()
		g1_1.addWidget(opmode_lbl,0,0)
		g1_1.addWidget(self.combo4,1,0)
		g1_1.addWidget(scanmode_lbl,0,1)
		g1_1.addWidget(self.combo5,1,1)
		g1_1.addWidget(resetmode_lbl,0,2)
		g1_1.addWidget(self.combo6,1,2)
		g1_1.addWidget(smartscan_lbl,0,3)
		g1_1.addWidget(self.cb_smartscan,1,3)
		
		g1_2 = QGridLayout()
		g1_2.addWidget(dwelltime_lbl,0,0)
		g1_2.addWidget(self.dwelltimeEdit,1,0)
		g1_2.addWidget(schroll_lbl,0,1)
		g1_2.addWidget(self.combo2,1,1)
		
		g1_4 = QGridLayout()
		for tal in range(2):
			g1_4.addWidget(self.xy_limiterEdit[tal],0,tal)
		
		v1_ = QVBoxLayout()
		v1_.addWidget(xy_limiter_lbl)
		v1_.addLayout(g1_4)
		
		h1_ = QHBoxLayout()
		h1_.addLayout(g1_2)
		h1_.addLayout(v1_)
			
		v1 = QVBoxLayout()
		v1.addLayout(g1_0)
		v1.addLayout(g1_1)
		v1.addLayout(h1_)
		
		#####################################################
		
		#g8_0 = QGridLayout()
		#g8_0.addWidget(lockin_lbl,0,0)
		g8_1 = QGridLayout()
		g8_1.addWidget(self.amp_lbl,0,0)
		g8_1.addWidget(self.sld_amp,1,0)
		g8_1.addWidget(self.freq_lbl,0,1)
		g8_1.addWidget(self.sld_freq,1,1)
		#g8_1.addWidget(rate_lbl,0,2)
		#g8_1.addWidget(self.freqEdit,1,2)
		v8 = QVBoxLayout()
		#v8.addLayout(g8_0)
		v8.addLayout(g8_1)
		
		#####################################################
		
		g2_0 = QGridLayout()
		g2_0.addWidget(lbl7,0,0)
		
		g2_1 = QGridLayout()
		g2_1.addWidget(start_lbl,0,1)
		g2_1.addWidget(stop_lbl,0,2)
		g2_1.addWidget(step_lbl,0,3)
		g2_1.addWidget(self.absrel_lbl,0,4)
		g2_1.addWidget(actual_lbl,0,5)
		
		for tal in range(2):
			g2_1.addWidget(xy_lbl[tal],1+tal,0)
		for tal in range(3):
			g2_1.addWidget(self.xscanEdit[tal],1,1+tal)
			g2_1.addWidget(self.yscanEdit[tal],2,1+tal)
		for tal in range(2):
			g2_1.addWidget(self.absrelEdit[tal],1+tal,4)
		for tal in range(2):
			g2_1.addWidget(self.lcd_actual[tal],1+tal,5)
		
		v2 = QVBoxLayout()
		v2.addLayout(g2_0)
		v2.addLayout(g2_1)

		
		#####################################################
		
		g5_0 = QGridLayout()
		g5_0.addWidget(lbl5,0,0)
		
		g5_1 = QGridLayout()
		g5_1.addWidget(self.runButton,0,1)
		g5_1.addWidget(self.cancelButton,0,2)
		
		v5 = QVBoxLayout()
		v5.addLayout(g5_0)
		v5.addLayout(g5_1)
		
		#####################################################
		
		g6_0 = QGridLayout()
		g6_0.addWidget(lbl4,0,0)
		g6_1 = QGridLayout()
		g6_1.addWidget(txtfile_lbl,0,0)
		g6_1.addWidget(self.txtfile_,0,1)
		g6_1.addWidget(dbfile_lbl,1,0)
		g6_1.addWidget(self.dbfile_,1,1)
		g6_1.addWidget(matfile_lbl,2,0)
		g6_1.addWidget(self.matfile_,2,1)
		g6_2 = QGridLayout()
		g6_2.addWidget(self.lcd_time,0,0)
		v6 = QVBoxLayout()
		v6.addLayout(g6_0)
		v6.addLayout(g6_1)
		v6.addLayout(g6_2)
		
		#####################################################
		
		# add ALL groups from v1 to v6 in one vertical group v7
		v7 = QVBoxLayout()
		v7.addLayout(v1)
		v7.addLayout(v8)
		v7.addLayout(v2)
		v7.addLayout(v6)
		v7.addLayout(v5)
	
		#####################################################
		
		# set GRAPHS and TOOLBARS to a new vertical group vcan
		win2 = pg.GraphicsWindow()
		vcan0 = QGridLayout()
		vcan0.addWidget(win2,0,0)
		
		# SET ALL HORIZONTAL COLUMNS TOGETHER
		hbox = QHBoxLayout()
		hbox.addLayout(v7)
		hbox.addLayout(vcan0)
		
		
		vcan1 = QGridLayout()
		self.pw3 = pg.PlotWidget()
		vcan1.addWidget(self.pw3,0,0)
		
		# SET VERTICAL COLUMNS TOGETHER TO FINAL LAYOUT
		vbox = QVBoxLayout()
		vbox.addLayout(hbox)
		vbox.addLayout(vcan1)
		
		
		win = pg.GraphicsWindow()
		#win.resize(1000,600)
		vcan2 = QGridLayout()
		vcan2.addWidget(win,0,0)
		
		# SET HORIZONTAL COLUMNS TOGETHER TO FINAL LAYOUT
		hbox1 = QHBoxLayout()
		hbox1.addLayout(vbox)
		hbox1.addLayout(vcan2)
		
		##############################################
		
		# INITIAL SETTINGS PLOT 1
		
		self.p0 = win2.addPlot()
		self.curve1 = self.p0.plot(pen='w', symbol='s', symbolPen='w', symbolBrush='b', symbolSize=4)
		self.curve2 = self.p0.plot(pen='k', symbol='s', symbolPen='k', symbolSize=6)
	
		self.p0.enableAutoRange()
		self.p0.setTitle(''.join(["2-D scan, Jet colormap"]))
		self.p0.setLabel('left', "Y", units='m', color='red')
		self.p0.setLabel('bottom', "X", units='m', color='red')
		
		win2.nextRow()
		
		self.p11 = win2.addPlot()
		self.curve11 = self.p11.plot(pen='y')
		self.curve12 = self.p11.plot(pen=None, symbol='s', symbolPen='m', symbolBrush='m', symbolSize=6)
		self.curve13 = self.p11.plot(pen={'color':'m','width':1}, symbol='o', symbolPen='w', symbolBrush='b', symbolSize=6)
		
		self.my_text = pg.TextItem("FWHM", anchor=(0.5,-0.75))
		self.my_text.setParentItem(self.curve13)
		self.my_arrow = pg.ArrowItem(angle=90)
		self.my_arrow.setParentItem(self.curve13)
		
		
		self.p11.enableAutoRange()
		self.p11.setTitle(''.join(["Latest gaussian fit"]), color='y')
		self.p11.setLabel('left', "U", units='V', color='yellow')
		self.p11.setLabel('bottom', "X or Y", units='m', color='yellow')
		
		
		# INITIAL SETTINGS PLOT 2
		p6 = win.addPlot()
		self.curve6=p6.plot(pen='w', symbol='o', symbolPen='w',symbolSize=8)
		p6.setTitle(''.join(["Mapping (X,Y) -> S"]))
		p6.setLabel('left', "U_max", units='V', color='white')
		p6.setLabel('bottom', "S", units='m', color='white')
		p6.setLogMode(y=True)
		p6.enableAutoRange()
		
		win.nextRow()
		
		# INITIAL SETTINGS PLOT 5
		p8 = win.addPlot()
		self.curve8=p8.plot(pen='r', symbol='o', symbolPen='w',symbolSize=8)
		self.curve7=p8.plot(pen=None, symbol='o', symbolPen=None, symbolBrush='y', symbolSize=8)
		p8.setTitle(''.join(["U_max positions"]))
		p8.setLabel('left', "Y", units='m', color='red')
		p8.setLabel('bottom', "X", units='m', color='red')
		p8.enableAutoRange()
		
		win.nextRow()
		
		# INITIAL SETTINGS PLOT 6
		p9 = win.addPlot()
		self.curve9=p9.plot(pen='m', symbol='d', symbolPen='m',symbolSize=8)
		p9.setTitle(''.join(["FWHM by spline"]))
		p9.setLabel('left', "FWHM", units='m', color='magenta')
		p9.setLabel('bottom', "Index of axis scanned", color='magenta')
		
		win.nextRow()
		
		# INITIAL SETTINGS PLOT 7
		p10 = win.addPlot()
		self.curve10=p10.plot(pen='y', symbol='d', symbolPen='y',symbolSize=8)
		p10.setTitle(''.join(["Attenuation slope a"]))
		p10.setLabel('left', "a", units='dB/cm', color='yellow')
		p10.setLabel('bottom', "Index of axis scanned", color='yellow')
		
		# INITIAL SETTINGS PLOT 3
		self.p1 = self.pw3.plotItem
		self.curve3=self.p1.plot(pen='w')
		self.curve4=self.p1.plot(pen='y')
		# create plot and add it to the figure
		self.p2 = pg.ViewBox()
		self.curve5=pg.PlotCurveItem(pen='r')
		self.p2.addItem(self.curve5)
		# connect respective axes to the plot 
		self.p1.scene().addItem(self.p2)
		self.p1.getAxis('right').linkToView(self.p2)
		self.p2.setXLink(self.p1)
		# Use automatic downsampling and clipping to reduce the drawing load
		self.pw3.setDownsampling(mode='peak')
		self.pw3.setClipToView(True)
		self.pw3.enableAutoRange()
		# Labels and titels are placed here since they change dynamically
		self.pw3.setTitle(''.join(["Voltage and position as function of time"]))
		self.pw3.setLabel('left', "Lock-in voltage", units='V', color='yellow')
		self.pw3.setLabel('right', "Scan axis", units='m', color='red')
		self.pw3.setLabel('bottom', "Elapsed time", units='s', color='white')
		'''
		# INITIAL SETTINGS PLOT 4
		self.pw4 = gl.GLViewWidget()
		self.pw4.opts['distance'] = 0.03
		self.pw4.setWindowTitle('Scatter plot of sweeped poins')
		
		#zx = gl.GLGridItem()
		#zx.rotate(90, 0, 1, 0) # zx-plane
		#zx.translate(-1, 0, 0)
		#zx.scale(0.1,0.1,0.1,local=True)
		#self.pw4.addItem(zx)
		
		zy = gl.GLGridItem()
		zy.rotate(90, 1, 0, 0) # zy-plane
		zy_spacing=1e-3 # Volts
		zy.translate(0, 0, 10*zy_spacing)
		zy.scale(zy_spacing,zy_spacing,zy_spacing,local=True)
		self.pw4.addItem(zy)
		
		xy = gl.GLGridItem()
		xy_spacing=1e-3 # Meters
		xy.translate(0, -10*xy_spacing, 0) # xy-plane
		xy.scale(xy_spacing,xy_spacing,xy_spacing,local=True)
		self.pw4.addItem(xy)
		## create a new AxisItem, linked to view
		#ax2 = gl.GLAxisItem()
		#ax2.setSize(x=10,y=10,z=10)
		#self.pw4.addItem(ax2)
		#ax2.setLabel('latitude', color='#0000ff')
		self.sp1 = gl.GLScatterPlotItem()
		'''
		# Initialize and set titles and axis names for both plots
		
		##############################################
		
		# reacts to drop-down menus
		self.combo2.activated[str].connect(self.onActivated2)
		self.combo4.activated[str].connect(self.onActivated4)
		self.combo5.activated[str].connect(self.onActivated5)
		self.combo6.activated[str].connect(self.onActivated6)
		self.cb_smartscan.toggled.connect(self.smartscan)
		self.sld_freq.valueChanged[int].connect(self.changeFreq)
		self.sld_amp.valueChanged[int].connect(self.changeAmp)
	
		# run the main script
		self.runButton.clicked.connect(self.set_run)
		
		# cancel the script run
		self.cancelButton.clicked.connect(self.abort)
		
		self.clear_vars_graphs()
		self.allFields(False)
		
		self.disconMode.setEnabled(False)
		self.cancelButton.setEnabled(False)
		self.runButton.setEnabled(False)
		self.fileClose.setEnabled(True)
		
		self.threadpool = QThreadPool()
		print("Multithreading in Run_it6d_ca2_GUI_ver16 with maximum %d threads" % self.threadpool.maxThreadCount())
		self.isRunning = False
		
		self.timer = QTimer(self)
		self.timer.timeout.connect(self.set_disconnect)
		self.timer.setSingleShot(True)
		
		self.setGeometry(10, 10, 1300, 1100)
		#self.move(0,0)
		self.setWindowTitle("IT6D CA2 Microstepper And SR810 Lock-In Data Acqusition")
		
		w = QWidget()
		w.setLayout(hbox1)
		self.setCentralWidget(w)
		self.show()
		
		
	def initUI_(self):
		
		self.combo2.setCurrentIndex(self.mylist2.index(str(self.schroll_pts)))
		
		self.combo4.setCurrentIndex(self.mylist4.index(self.op_mode))
		
		self.combo5.setCurrentIndex(self.mylist5.index(self.scan_mode))
		
		self.combo6.setCurrentIndex(self.mylist6.index(self.reset_mode))
		
		for i in range(2):
			self.xy_limiterEdit[i].setText(self.xy_limiter_mm[i])
			self.xy_limiterEdit[i].setFixedWidth(50)
			
		self.cb_smartscan.setChecked(self.smartscan_check)
		
		#####################################################
		
		self.amp_lbl.setText(''.join(["Osc. Vpk-pk (",str(self.lockin_volt),") [V]"]))
		self.sld_amp.setValue(int(1000*self.lockin_volt))
		
		self.freq_lbl.setText(''.join(["Osc. freq (",str(self.lockin_freq),") [Hz]"]))
		self.sld_freq.setValue(self.lockin_freq)
		
		#####################################################
		
		for i in range(3):
			self.xscanEdit[i].setText(self.xscan[i])
			self.yscanEdit[i].setText(self.yscan[i])
		for i in range(2):
			self.absrelEdit[i].setText(self.absrel_mm[i])
		
		#####################################################
		
		if self.write2txt_check:
			self.txtfile_.setText(''.join([self.write2txt_str,' (.txt)']))
			self.txtfile_.setStyleSheet("color: green")
		else:
			self.txtfile_.setText("No text file")
			self.txtfile_.setStyleSheet("color: red")
			
		if self.write2db_check:
			self.dbfile_.setText(''.join([self.write2db_str,' (.db)']))
			self.dbfile_.setStyleSheet("color: green")
		else:
			self.dbfile_.setText("No database file")
			self.dbfile_.setStyleSheet("color: red")
		
		if self.write2mat_check:
			self.matfile_.setText(''.join([self.write2mat_str,' (.mat)']))
			self.matfile_.setStyleSheet("color: green")
		else:
			self.matfile_.setText("No matlab file")
			self.matfile_.setStyleSheet("color: red")
		
		#####################################################
		
		self.lcd_time.display(self.timestr)
			
		#####################################################
		
		
	def set_connect(self):
		
		try:
			self.sr810 = SR810.SR810(self.sr810port_str)
		except Exception as e:
			QMessageBox.critical(self, 'Message',"No response from SR810 serial port! Check the serial port name.")
			return
		
		try:
			self.sr810.set_to_rs232()
			self.sr810.set_timeout(1)
			self.sr810.set_intrl_volt(int(1000*self.lockin_volt)/1000)
			self.sr810.set_intrl_freq(self.lockin_freq)
			val=self.sr810.return_id()
			if not val:
				self.sr810.close()
				QMessageBox.warning(self, 'Message',"No response from SR810 lock-in amplifier! Is SR810 powered and connected to serial?")
				return
		except Exception as e:
			self.sr810.close()
			QMessageBox.warning(self, 'Message',"No response from SR810 lock-in amplifier! Is SR810 powered and connected to serial?")
			return
		
		try:
			self.it6d = IT6D_CA2_gpib.IT6D_CA2(int(self.it6d_ca2port_str))
		except Exception as e:
			QMessageBox.critical(self, 'Message',"No response from IT6D_CA2 microstepper Gpib port! Check the Gpib port name.")	
			return
		
		try:
			i_,j_ = self.it6d.get_positions()
		except Exception as e:
			QMessageBox.warning(self, 'Message',"No response from IT6D_CA2 microstepper! Is IT6D_CA2 powered and connected to Gpib?")	
			return
		
		self.lcd([1e-6*int(i_),1e-7*int(j_)])
		self.onActivated4(self.op_mode)
		self.conMode.setEnabled(False)
		self.disconMode.setEnabled(True)
		self.write2file.setEnabled(True)
		self.serSR810.setEnabled(False)
		self.gpibIT6D_CA2.setEnabled(False)
		self.timer.start(1000*60*5)
		
		
	def set_disconnect(self):

		self.sr810.close()
		
		self.allFields(False)
		self.conMode.setEnabled(True)
		self.disconMode.setEnabled(False)
		self.serSR810.setEnabled(True)
		self.gpibIT6D_CA2.setEnabled(True)
		self.timer.stop()
		
		
	def allFields(self,trueorfalse):
		
		self.combo2.setEnabled(trueorfalse)
		self.combo4.setEnabled(trueorfalse)
		self.combo5.setEnabled(trueorfalse)
		self.combo6.setEnabled(trueorfalse)
		self.cb_smartscan.setEnabled(trueorfalse)
		self.write2file.setEnabled(trueorfalse)
		
		self.sld_freq.setEnabled(trueorfalse)
		self.sld_amp.setEnabled(trueorfalse)
		self.dwelltimeEdit.setEnabled(trueorfalse)
		
		for i in range(2):
			self.xy_limiterEdit[i].setEnabled(trueorfalse)
		for i in range(3):
			self.xscanEdit[i].setEnabled(trueorfalse)
			self.yscanEdit[i].setEnabled(trueorfalse)
		for i in range(2):
			self.absrelEdit[i].setEnabled(trueorfalse)
			
		self.runButton.setEnabled(trueorfalse)
		
		
	def IT6D_CA2Dialog(self):

		text, ok = QInputDialog.getText(self, 'Gpib Port Dialog','Enter IT6D_CA2 microstepper port:', text=self.it6d_ca2port_str)
		if ok:
			self.it6d_ca2port_str = str(text)
			
			
	def SR810Dialog(self):

		text, ok = QInputDialog.getText(self, 'Serial Port Dialog','Enter SR810 lock-in port:', text=self.sr810port_str)
		if ok:
			self.sr810port_str = str(text)
			
			
	def write2fileDialog(self):
		
		self.Write2file_dialog = Write2file_dialog.Write2file_dialog(self, self.config)
		self.Write2file_dialog.exec()
		
		try:
			self.write2txt_str=self.config.get(self.last_used_scan,'write2txt').strip().split(',')[0]
			self.write2txt_check=self.bool_(self.config.get(self.last_used_scan,'write2txt').strip().split(',')[1])
			self.write2db_str=self.config.get(self.last_used_scan,'write2db').strip().split(',')[0]
			self.write2db_check=self.bool_(self.config.get(self.last_used_scan,'write2db').strip().split(',')[1])
			self.write2mat_str=self.config.get(self.last_used_scan,'write2mat').strip().split(',')[0]
			self.write2mat_check=self.bool_(self.config.get(self.last_used_scan,'write2mat').strip().split(',')[1])
		except configparser.NoOptionError as nov:
			QMessageBox.critical(self, 'Message',''.join(["Main FAULT while reading the config.ini file\n",str(nov)]))
			return
		
		if self.write2txt_check:
			self.txtfile_.setText(''.join([self.write2txt_str,' (.txt)']))
			self.txtfile_.setStyleSheet("color: green")
		else:
			self.txtfile_.setText("No text file")
			self.txtfile_.setStyleSheet("color: red")
		
		if self.write2db_check:
			self.dbfile_.setText(''.join([self.write2db_str,' (.db)']))
			self.dbfile_.setStyleSheet("color: green")
		else:
			self.dbfile_.setText("No database file")
			self.dbfile_.setStyleSheet("color: red")
			
		if self.write2mat_check:
			self.matfile_.setText(''.join([self.write2mat_str,' (.mat)']))
			self.matfile_.setStyleSheet("color: green")
		else:
			self.matfile_.setText("No matlab file")
			self.matfile_.setStyleSheet("color: red")
			
			
	def load_config_dialog(self):
		
		self.Load_config_dialog = Load_config_dialog.Load_config_dialog(self, self.config, self.load_, self.initUI_, self.cwd)
		self.Load_config_dialog.exec()
		
		
	def email_data_dialog(self):
		
		self.Send_email_dialog = Send_email_dialog.Send_email_dialog(self, self.cwd)
		self.Send_email_dialog.exec()
		
		
	def email_set_dialog(self):
		
		self.Email_dialog = Email_settings_dialog.Email_dialog(self, self.lcd_time, self.cwd)
		self.Email_dialog.exec()
		
		
	def changeFreq(self, val):
		
		self.lockin_freq=val
		self.freq_lbl.setText(''.join(["Osc. freq (",str(val),") [Hz]"]))
		if hasattr(self, 'sr810'):
			self.sr810.set_intrl_freq(val)
			time.sleep(0.05)
		
		
	def changeAmp(self, val):
		
		self.lockin_volt=val/1000
		self.amp_lbl.setText(''.join(["Osc. Vpk-pk (",str(val/1000),") [V]"]))
		if hasattr(self, 'sr810'):
			self.sr810.set_intrl_volt(val/1000)
			time.sleep(0.05)
		
		
	def onActivated2(self, text):
		self.schroll_pts=int(text)
	
	
	def onActivated6(self, text):
		self.reset_mode = str(text)
	
	
	def smartscan(self):
		
		if self.cb_smartscan.isChecked():
			self.smartscan_check = True
		else:
			self.smartscan_check = False
		
		
	def onActivated5(self, text):
		self.scan_mode = str(text)
	
	
	def onActivated4(self, text):
		
		self.op_mode = str(text)
		self.combo4.setEnabled(True)
		self.cancelButton.setEnabled(False)
		self.runButton.setEnabled(True)
		self.fileClose.setEnabled(True)
		self.sld_freq.setEnabled(True)
		self.sld_amp.setEnabled(True)
		
		if self.op_mode=='xyscan':
			self.combo2.setEnabled(True)
			self.combo5.setEnabled(True)
			self.combo6.setEnabled(False)
			self.cb_smartscan.setEnabled(True)
			self.dwelltimeEdit.setEnabled(True)
			for i in range(2):
				self.xy_limiterEdit[i].setEnabled(True)
			for i in range(3):
				self.xscanEdit[i].setEnabled(True)
				self.yscanEdit[i].setEnabled(True)
			for i in range(2):
				self.absrelEdit[i].setEnabled(False)
		
		elif self.op_mode=='xscan':
			self.combo2.setEnabled(True)
			self.combo5.setEnabled(False)
			self.combo6.setEnabled(False)
			self.cb_smartscan.setEnabled(False)
			self.dwelltimeEdit.setEnabled(True)
			self.xy_limiterEdit[0].setEnabled(True)
			self.xy_limiterEdit[1].setEnabled(False)
			for i in range(3):
				self.xscanEdit[i].setEnabled(True)
				self.yscanEdit[i].setEnabled(False)
			for i in range(2):
				self.absrelEdit[i].setEnabled(False)
				
		elif self.op_mode=='yscan':
			self.combo2.setEnabled(True)
			self.combo5.setEnabled(False)
			self.combo6.setEnabled(False)
			self.cb_smartscan.setEnabled(False)
			self.dwelltimeEdit.setEnabled(True)
			self.xy_limiterEdit[0].setEnabled(False)
			self.xy_limiterEdit[1].setEnabled(True)
			for i in range(3):
				self.xscanEdit[i].setEnabled(False)
				self.yscanEdit[i].setEnabled(True)
			for i in range(2):
				self.absrelEdit[i].setEnabled(False)
		
		elif self.op_mode in ['move abs','move rel']:
			if self.op_mode=='move rel':
				self.absrel_lbl.setText('Rel')
			elif self.op_mode=='move abs':
				self.absrel_lbl.setText('Abs')
			self.combo2.setEnabled(False)
			self.combo5.setEnabled(False)
			self.combo6.setEnabled(False)
			self.cb_smartscan.setEnabled(False)
			self.dwelltimeEdit.setEnabled(False)
			for i in range(2):
				self.xy_limiterEdit[i].setEnabled(True)
			for i in range(3):
				self.xscanEdit[i].setEnabled(False)
				self.yscanEdit[i].setEnabled(False)
			for i in range(2):
				self.absrelEdit[i].setEnabled(True)

		elif self.op_mode=='reset':
			self.combo2.setEnabled(False)
			self.combo5.setEnabled(False)
			self.combo6.setEnabled(True)
			self.cb_smartscan.setEnabled(False)
			self.dwelltimeEdit.setEnabled(False)
			for i in range(2):
				self.xy_limiterEdit[i].setEnabled(False)
			for i in range(3):
				self.xscanEdit[i].setEnabled(False)
				self.yscanEdit[i].setEnabled(False)
			for i in range(2):
				self.absrelEdit[i].setEnabled(False)
		else:
			pass
		
		
	def create_file(self,mystr):
		
		head, tail = os.path.split(mystr)
		# Check for possible name conflicts
		if tail:
			saveinfile=''.join([tail,self.timestr])
		else:
			saveinfile=''.join(["data_",self.timestr])
			
		if head:
			if not os.path.isdir(head):
				os.mkdir(head)
			saveinfolder=''.join([head,"/"])
		else:
			saveinfolder=""
			
		return ''.join([saveinfolder,saveinfile])
	
	
	def prepare_file(self):
		# Save to a textfile
		if self.write2txt_check:
			self.textfile=''.join([self.create_file(self.write2txt_str),".txt"])	
			self.textfile_spine=''.join([self.textfile[:-4],"_spine.txt"])
			
			with open(self.textfile, 'w') as thefile:
				thefile.write("Your comment line - do NOT delete this line\n")
				thefile.write("Col 0: X-pos [m]\nCol 1: Y-pos [m]\nCol 2: Voltage [V]\nCol 3: Time [sec]\n\n")
				thefile.write('%s\t\t%s\t\t%s\t\t%s\n' %(tuple(''.join(["Col ",str(tal)]) for tal in range(4))))
			
			if self.op_mode=="xyscan":
				with open(self.textfile_spine, 'w') as thefile:
					thefile.write("Your comment line - do NOT delete this line\n")
					thefile.write("Col 0: Axis index\nCol 1: S_path [m]\n")
					thefile.write("Col 2: Max voltage X-pos[m]\nCol 3: Max voltage Y-pos[m]\n")
					thefile.write("Col 4: Max voltage [V]\nCol 5: Full width half maximum (FWHM) [m]\n\n")
					thefile.write('%s\t%s\t%s\t%s\t%s\t%s\n' %(tuple(''.join(["Col ",str(tal)]) for tal in range(6))))
			
			elif self.op_mode in ["xscan","yscan"]:
				with open(self.textfile_spine, 'w') as thefile:
					thefile.write("Your comment line - do NOT delete this line\n")
					thefile.write("Axis index\t Full width half maximum (FWHM) [m]\n")
					
		# Save to a MATLAB datafile
		if self.write2mat_check:
			self.matfile = ''.join([self.create_file(self.write2mat_str),".mat"])
		
		# Save to a SQLite database file
		# First delete the database file if it exists
		if self.write2db_check:
			self.dbfile = ''.join([self.create_file(self.write2db_str),".db"])
			try:
				os.remove(self.dbfile)
			except OSError:
				pass
			
			# Then create it again for new inputs
			self.conn = sqlite3.connect(self.dbfile)
			self.db = self.conn.cursor()
			self.db.execute('''CREATE TABLE scan (xpos real, ypos real, voltage real, timetrace real)''')
			
			if self.op_mode=="xyscan":
				self.db.execute('''CREATE TABLE spine (idx real, Spath real, xpos real, ypos real, Umax real, fwhm real)''')
			
			elif self.op_mode in ["xscan","yscan"]:
				self.db.execute('''CREATE TABLE spine (idx real, fwhm real)''')
					
					
	def set_run(self):
		
		xy_limiter=[float(self.xy_limiterEdit[tal].text()) for tal in range(2)]
		i_,j_ = self.it6d.get_positions()
		
		if self.op_mode=='xyscan':
			# Initial read of the config file
			xx = [int(1000*float(self.xscanEdit[ii].text())) for ii in range(3)]
			yy = [int(10000*float(self.yscanEdit[ii].text())) for ii in range(3)]
			sm = Methods_for_IT6D_CA2.Scan_methods(xx[0],xx[1],xx[2],yy[0],yy[1],yy[2])
			
			xf=Methods_for_IT6D_CA2.Myrange(xx[0],xx[1],xx[2])
			x_fields=xf.myrange() # 1 unit = 1 um
			
			yf=Methods_for_IT6D_CA2.Myrange(yy[0],yy[1],yy[2])
			y_fields=yf.myrange() # 1 unit = 0.1 um
			
			dwelltime = float(self.dwelltimeEdit.text())
			xscan = [float(self.xscanEdit[ii].text()) for ii in range(3)]
			yscan = [float(self.yscanEdit[ii].text()) for ii in range(3)]
			i_vals,j_vals = sm.run(self.scan_mode)
			
			if abs(xscan[0]-int(i_)/1000)>xy_limiter[0] or abs(xscan[1]-int(i_)/1000)>xy_limiter[0]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the X direction limited to ", str(xy_limiter[0]) ,' mm' ]))
			elif abs(yscan[0]-int(j_)/10000)>xy_limiter[1] or abs(yscan[1]-int(j_)/10000)>xy_limiter[1]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the Y direction limited to ", str(xy_limiter[1]) ,' mm' ]))
			elif len(x_fields)<3 or len(y_fields)<3:
				QMessageBox.warning(self, 'Message',''.join([ "Number of scan points is minimum 3 along X-axis and along Y-axis" ]))
			else:
				all_pts=len(x_fields)*len(y_fields)*dwelltime+sum(abs(numpy.diff(i_vals)))/380+sum(abs(numpy.diff(j_vals)))/350
				mi,se=divmod(int(all_pts),60)
				ho,mi=divmod(mi,60)
				da,ho=divmod(ho,24)
				if self.smartscan_check:
					if mi==0 and ho==0 and da==0:
						msg=''.join(["Smart scan is activated. The xyscan will take ",str(se)," seconds. Continue?"])
					elif ho==0 and da==0:
						msg=''.join(["Smart scan is activated. The xyscan will take ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
					elif da==0:
						msg=''.join(["Smart scan is activated. The xyscan will take ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
					else:
						msg=''.join(["Smart scan is activated. The xyscan will take ",str(da)," day(s), ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				else:
					if mi==0 and ho==0 and da==0:
						msg=''.join(["The xyscan will take ",str(se)," seconds. Continue?"])
					elif ho==0 and da==0:
						msg=''.join(["The xyscan will take ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
					elif da==0:
						msg=''.join(["The xyscan will take ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
					else:
						msg=''.join(["The xyscan will take ",str(da)," day(s), ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes | QMessageBox.No)
				if reply == QMessageBox.Yes:
					pass
				else:
					return None
				self.prepare_file()
				self.timer.stop()
				self.isRunning = True
				self.clear_vars_graphs()
				self.allFields(False)
				self.cancelButton.setEnabled(True)
				self.runButton.setEnabled(False)
				self.fileClose.setEnabled(False)
				self.disconMode.setEnabled(False)
				self.all_xy(i_vals*1e-6,j_vals*1e-7) # convert to meters
				
				obj = type('setscan_obj',(object,),{'op_mode':self.op_mode, 'scan_mode':self.scan_mode, 'dwell_time':dwelltime, 'smart_scan':self.smartscan_check, 'xscan':x_fields,'yscan':y_fields,'reset_mode':self.reset_mode, 'it6d':self.it6d, 'sr810':self.sr810})
				self.worker=IT6D_CA2_Worker(obj)
				
				self.worker.signals.lcd.connect(self.lcd)
				self.worker.signals.update2.connect(self.update2)
				self.worker.signals.update4.connect(self.update4)
				self.worker.signals.color_map.connect(self.color_map)
				
				self.worker.signals.fwhm_2D.connect(self.fwhm_2D)
				self.worker.signals.slope.connect(self.slope)
				self.worker.signals.make_3Dplot.connect(self.make_3Dplot)
				self.worker.signals.plot_gaussian.connect(self.plot_gaussian)
				
				self.worker.signals.Umax.connect(self.Umax)
				self.worker.signals.Spath.connect(self.Spath)
				self.worker.signals.pos_lcd.connect(self.pos_lcd)
				
				self.worker.signals.warning.connect(self.warning)
				self.worker.signals.finished.connect(self.finished)
				
				# Execute
				self.threadpool.start(self.worker)
				
				
		elif self.op_mode=='xscan':
			# Set the internal oscillator on SR810
			
			# Initial read of the config file
			xscan = [float(self.xscanEdit[ii].text()) for ii in range(3)]
			xx = [int(1000*float(self.xscanEdit[ii].text())) for ii in range(3)]
			xf=Methods_for_IT6D_CA2.Myrange(xx[0],xx[1],xx[2])
			x_fields=xf.myrange() # 1 unit = 1 um
			
			dwelltime = float(self.dwelltimeEdit.text())
			
			i_vals=x_fields
			j_vals=numpy.array([int(j_) for jj in range(len(x_fields))])
			
			if abs(xscan[0]-int(i_)/1000)>xy_limiter[0] or abs(xscan[1]-int(i_)/1000)>xy_limiter[0]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the X direction limited to ", str(xy_limiter[0]) ,' mm' ]))
			elif len(x_fields)<3:
				QMessageBox.warning(self, 'Message',''.join([ "Number of scan points is minimum 3 along X-axis" ]))
			else:
				all_pts=len(x_fields)*dwelltime+sum(abs(numpy.diff(i_vals)))/380
				mi,se=divmod(int(all_pts),60)
				ho,mi=divmod(mi,60)
				da,ho=divmod(ho,24)
				if mi==0 and ho==0 and da==0:
					msg=''.join(["The xscan will take ",str(se)," seconds. Continue?"])
				elif ho==0 and da==0:
					msg=''.join(["The xscan will take ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				elif da==0:
					msg=''.join(["The xscan will take ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				else:
					msg=''.join(["The xscan will take ",str(da)," day(s), ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes | QMessageBox.No)
				if reply == QMessageBox.Yes:
					pass
				else:
					return None
				self.prepare_file()
				self.timer.stop()
				self.isRunning = True
				self.clear_vars_graphs()
				self.allFields(False)
				self.cancelButton.setEnabled(True)
				self.runButton.setEnabled(False)
				self.fileClose.setEnabled(False)
				self.disconMode.setEnabled(False)
				self.all_xy(i_vals*1e-6,j_vals*1e-7) # convert to meters
				
				obj = type('setscan_obj',(object,),{'op_mode':self.op_mode, 'scan_mode':self.scan_mode, 'dwell_time':dwelltime, 'xscan':x_fields,'reset_mode':self.reset_mode, 'it6d':self.it6d, 'sr810':self.sr810})
				self.worker=IT6D_CA2_Worker(obj)
				
				self.worker.signals.pos_lcd.connect(self.pos_lcd)
				self.worker.signals.update2.connect(self.update2)
				self.worker.signals.update4.connect(self.update4)
				self.worker.signals.color_map.connect(self.color_map)
				self.worker.signals.fwhm_1D.connect(self.fwhm_1D)
				self.worker.signals.plot_gaussian.connect(self.plot_gaussian)
				self.worker.signals.Umax.connect(self.Umax)
				
				self.worker.signals.warning.connect(self.warning)
				self.worker.signals.finished.connect(self.finished)
				
				# Execute
				self.threadpool.start(self.worker)
				
		elif self.op_mode=='yscan':
			# Set the internal oscillator on SR810
			
			# Initial read of the config file
			yscan = [float(self.yscanEdit[ii].text()) for ii in range(3)]
			yy = [int(10000*float(self.yscanEdit[ii].text())) for ii in range(3)]
			yf=Methods_for_IT6D_CA2.Myrange(yy[0],yy[1],yy[2])
			y_fields=yf.myrange() # 1 unit = 0.1 um
			dwelltime = float(self.dwelltimeEdit.text())
			
			j_vals=y_fields
			i_vals=numpy.array([int(i_) for ii in range(len(y_fields))])
			
			if abs(yscan[0]-int(j_)/10000)>xy_limiter[1] or abs(yscan[1]-int(j_)/10000)>xy_limiter[1]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the Y direction limited to ", str(xy_limiter[1]) ,' mm' ]))
			elif len(y_fields)<3:
				QMessageBox.warning(self, 'Message',''.join([ "Number of scan points is minimum 3 along Y-axis" ]))
			else:
				all_pts=len(y_fields)*dwelltime+sum(abs(numpy.diff(j_vals)))/350
				mi,se=divmod(int(all_pts),60)
				ho,mi=divmod(mi,60)
				da,ho=divmod(ho,24)
				if mi==0 and ho==0 and da==0:
					msg=''.join(["The yscan will take ",str(se)," seconds. Continue?"])
				elif ho==0 and da==0:
					msg=''.join(["The yscan will take ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				elif da==0:
					msg=''.join(["The yscan will take ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				else:
					msg=''.join(["The yscan will take ",str(da)," day(s), ",str(ho)," hour(s) and ",str(mi)," minutes and ",str(se)," seconds. Continue?"])
				reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes | QMessageBox.No)
				if reply == QMessageBox.Yes:
					pass
				else:
					return None
				self.prepare_file()
				self.timer.stop()
				self.isRunning = True
				self.clear_vars_graphs()
				self.allFields(False)
				self.cancelButton.setEnabled(True)
				self.runButton.setEnabled(False)
				self.fileClose.setEnabled(False)
				self.disconMode.setEnabled(False)
				self.all_xy(i_vals*1e-6,j_vals*1e-7) # convert to meters
				
				obj = type('setscan_obj',(object,),{'op_mode':self.op_mode, 'scan_mode':self.scan_mode, 'dwell_time':dwelltime, 'yscan':y_fields,'reset_mode':self.reset_mode, 'it6d':self.it6d, 'sr810':self.sr810})
				self.worker=IT6D_CA2_Worker(obj)
				
				self.worker.signals.update2.connect(self.update2)
				self.worker.signals.update4.connect(self.update4)
				self.worker.signals.color_map.connect(self.color_map)
				self.worker.signals.fwhm_1D.connect(self.fwhm_1D)
				self.worker.signals.plot_gaussian.connect(self.plot_gaussian)
				self.worker.signals.Umax.connect(self.Umax)
				self.worker.signals.pos_lcd.connect(self.pos_lcd)
				
				self.worker.signals.warning.connect(self.warning)
				self.worker.signals.finished.connect(self.finished)
				
				# Execute
				self.threadpool.start(self.worker)
				
		elif self.op_mode=='move abs':
			
			abss = [float(self.absrelEdit[ii].text()) for ii in range(2)]
			
			if abs(abss[0]-int(i_)/1000)>xy_limiter[0]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the X direction limited to ", str(xy_limiter[0]) ,' mm' ]))
			elif abs(abss[1]-int(j_)/10000)>xy_limiter[1]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the Y direction limited to ", str(xy_limiter[1]) ,' mm' ]))
			else:
				self.prepare_file()
				self.timer.stop()
				self.isRunning = True
				self.allFields(False)
				self.cancelButton.setEnabled(True)
				self.runButton.setEnabled(False)
				self.disconMode.setEnabled(False)
				abs_x = int(1000*float(self.absrelEdit[0].text())) 
				abs_y = int(10000*float(self.absrelEdit[1].text()))
				
				obj = type('setscan_obj',(object,),{'op_mode':self.op_mode, 'scan_mode':self.scan_mode, 'xscan':abs_x,'yscan':abs_y,'reset_mode':self.reset_mode, 'it6d':self.it6d, 'sr810':self.sr810})
				self.worker=IT6D_CA2_Worker(obj)
				
				self.worker.signals.lcd.connect(self.lcd)
				self.worker.signals.finished.connect(self.finished)
				
				# Execute
				self.threadpool.start(self.worker)
		
		elif self.op_mode=='move rel':
			
			rell = [float(self.absrelEdit[ii].text()) for ii in range(2)]
		
			if abs(rell[0]/1000)>xy_limiter[0]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the X direction limited to ", str(xy_limiter[0]) ,' mm' ]))
			elif abs(rell[1]/10000)>xy_limiter[1]:
				QMessageBox.warning(self, 'Message',''.join([ "All movements in the Y direction limited to ", str(xy_limiter[1]) ,' mm' ]))
			else:
				self.prepare_file()
				self.timer.stop()
				self.allFields(False)
				self.cancelButton.setEnabled(True)
				self.runButton.setEnabled(False)
				self.disconMode.setEnabled(False)
				rel_x = int(1000*float(self.absrelEdit[0].text())) 
				rel_y = int(10000*float(self.absrelEdit[1].text()))
				
				obj = type('setscan_obj',(object,),{'op_mode':self.op_mode, 'scan_mode':self.scan_mode, 'xscan':rel_x,'yscan':rel_y,'reset_mode':self.reset_mode, 'it6d':self.it6d, 'sr810':self.sr810})
				self.worker=IT6D_CA2_Worker(obj)
				
				self.worker.signals.lcd.connect(self.lcd)
				self.worker.signals.finished.connect(self.finished)
				
				# Execute
				self.threadpool.start(self.worker)
				
		elif self.op_mode=='reset':
			
			self.isRunning = True
			self.allFields(False)
			self.cancelButton.setEnabled(True)
			self.runButton.setEnabled(False)
			self.fileClose.setEnabled(False)
			self.disconMode.setEnabled(False)
			
			obj = type('setscan_obj',(object,),{'op_mode':self.op_mode, 'reset_mode':self.reset_mode, 'it6d':self.it6d})
			self.worker=IT6D_CA2_Worker(obj)
			
			self.worker.signals.lcd.connect(self.lcd)
			self.worker.signals.finished.connect(self.finished)
			
			# Execute
			self.threadpool.start(self.worker)
			
			
	def make_3Dplot(self):
		
		fig=plt.figure(figsize=(8,6))
		ax= fig.add_subplot(111, projection='3d')
		ax.plot_trisurf(1000*numpy.array(self.xpos_),1000*numpy.array(self.ypos_),1000*numpy.array(self.voltage_),cmap=cm.jet,linewidth=0.2)
		#ax=fig.gca(projection='2d')
		ax.set_xlabel('X[mm]')
		ax.set_ylabel('Y[mm]')
		ax.set_zlabel('U[mV]')
		
		if hasattr(self, 'textfile'):
			self.save_3Dplot=''.join([self.textfile[:-4],'_3D.png'])
		elif hasattr(self, 'matfile'):
			self.save_3Dplot=''.join([self.matfile[:-4],'_3D.png'])
		elif hasattr(self, 'dbfile'):
			self.save_3Dplot=''.join([self.dbfile[:-4],'_3D.png'])
		else:
			self.save_3Dplot=''.join([self.timestr,'_3D.png'])
		
		fig.savefig(self.save_3Dplot)
		
		
	'''
	def surf_line_plot(self):
		
		if self.scan_mode=='ywise':
			n = len(self.x_fields)
			x = self.x_fields
			y = self.y_fields
			z = self.acc_volt.reshape((len(self.x_fields),len(self.y_fields) ))
			for i in range(n):
				pts = (x,y,z[i,:])
				self.plt1.setData(pos=pts, color=pg.glColor((i,n*1.3)), width=(i+1)/10., antialias=True)
				self.pw4.addItem(self.plt1)
				
		elif self.scan_mode=='xwise':
			n = len(self.y_fields)
			x = self.x_fields
			y = self.y_fields
			z = self.acc_volt.reshape((len(self.x_fields),len(self.y_fields) ))
			for i in range(n):
				pts = (x,y,z[:,i])
				self.plt1.setData(pos=pts, color=pg.glColor((i,n*1.3)), width=(i+1)/10., antialias=True)
				self.pw4.addItem(self.plt1)
	'''
	
	
	def lcd(self,obj):
		# i and j are always in meters
		i,j = obj
		self.lcd_actual[0].display(str(numpy.round(i*1000,6))) # convert meters to mm
		self.lcd_actual[1].display(str(numpy.round(j*1000,7))) # convert meters to mm
		
		
	def pos_lcd(self,obj):
		# i and j are always in meters
		i,j = obj
		self.acc_x_pos.extend([ i ])
		self.acc_y_pos.extend([ j ])
		self.lcd_actual[0].display(str(numpy.round(i*1000,6))) # convert meters to mm
		self.lcd_actual[1].display(str(numpy.round(j*1000,7))) # convert meters to mm
		
			
	def color_map(self,volt):
		
		self.all_volt_endpts.extend([volt])
		my_norm = mpl.colors.Normalize(vmin=min(self.all_volt_endpts), vmax=max(self.all_volt_endpts))
		m = cm.ScalarMappable(norm=my_norm, cmap=mpl.cm.jet)
		my_color = m.to_rgba(self.all_volt_endpts,bytes=True)
		
		colors_=[]
		for i in my_color:
			colors_.append(pg.mkBrush(tuple(i)))
		
		self.curve2.setData(self.acc_x_pos, self.acc_y_pos, symbolBrush=colors_)
		
		'''
		spots3 = []
		for i,j,k in zip(self.acc_x_pos,self.acc_y_pos,my_color):
			spots3.append({'pos': (i, j), 'brush':tuple(k)})
		self.curve2.addPoints(spots3)
		'''
	
	
	def Spath(self,obj):
		
		umax_X_lsf,umax_Y_lsf,S,Umax = obj
		self.curve6.setData(S,Umax)
		self.curve8.setData(umax_X_lsf,umax_Y_lsf)
		
		
	def Umax(self,obj):
		
		umax_X,umax_Y = obj
		self.curve7.setData(umax_X,umax_Y)
		
		
	def fwhm_1D(self,obj):
		
		tals,fwhm_1D = obj
		
		if self.write2db_check:
			# Save to a database file
			for i in range(len(tals)):
				self.db.execute(''.join(["INSERT INTO spine VALUES (",str(tals[i]),",",str(fwhm_1D[i]),")"]))
				# Save (commit) the changes
				self.conn.commit()
		
		if self.write2txt_check:
			with open(self.textfile_spine, 'a') as thefile:
				for q,w in zip(tals,fwhm_1D):
					thefile.write('%s\t' %q)
					thefile.write('%s\n' %w)
		
		if self.write2mat_check:
			# save to a MATLAB file
			self.matdata['spine-index']=tals
			self.matdata['spine-fwhm']=fwhm_1D
		
		self.curve9.setData(tals,fwhm_1D)
		
		
	def fwhm_2D(self,obj):
		
		tals,S,save_x,save_y,save_Umax,fwhm_2D = obj
		
		if self.write2db_check:
			# Save to a database file
			for i in range(len(tals)):
				self.db.execute(''.join(["INSERT INTO spine VALUES (",str(tals[i]),",",str(S[i]),",",str(save_x[i]),",",str(save_y[i]),",",str(save_Umax[i]),",",str(fwhm_2D[i]),")"]))
				# Save (commit) the changes
				self.conn.commit()
			
		if self.write2txt_check:
			with open(self.textfile_spine, 'a') as thefile:
				for q,w,e,r,t,y in zip(tals,S,save_x,save_y,save_Umax,fwhm_2D):
					thefile.write('%s\t' %q)
					thefile.write('%s\t' %w)
					thefile.write('%s\t' %e)
					thefile.write('%s\t' %r)
					thefile.write('%s\t' %t)
					thefile.write('%s\n' %y)
		
		if self.write2mat_check:
			# save to a MATLAB file
			self.matdata['spine-index']=tals
			self.matdata['spine-s']=S
			self.matdata['spine-x']=save_x
			self.matdata['spine-y']=save_y
			self.matdata['spine-umax']=save_Umax
			self.matdata['spine-fwhm']=fwhm_2D
		
		self.curve9.setData(tals,fwhm_2D)
	
	
	def plot_gaussian(self,obj):
		
		pos_y,voltages,xy_string,save_xy,gauss_pos,gauss_volts,roots = obj
		
		if xy_string=='x':
			self.p11.setTitle(''.join(["Latest gaussian fit (X=",str(1000*save_xy),"mm)"]))
			self.p11.setLabel('bottom', "Y", units='m', color='yellow')
		elif xy_string=='y':
			self.p11.setTitle(''.join(["Latest gaussian fit (Y=",str(1000*save_xy),"mm)"]))
			self.p11.setLabel('bottom', "X", units='m', color='yellow')
		
		self.curve11.setData(gauss_pos,gauss_volts)
		self.curve12.setData(pos_y,voltages)
		self.curve13.setData(roots,2*[max(voltages)/2])
		
		self.my_text.setPos(numpy.mean(roots),max(voltages)/2)
		self.my_arrow.setPos(numpy.mean(roots),max(voltages)/2)
		
		
	def slope(self,obj):
		
		tals,slope=obj
		self.curve10.setData(tals,slope)
		
		
	def all_xy(self,i,j):
		
		if self.smartscan_check:
			self.curve1.setData(i,j, symbolBrush='k')
		else:
			self.curve1.setData(i,j)
			
			
	def update2(self,obj):
    
		time_elap,pos,volt = obj
		self.all_pos.extend([ pos ])
		if len(self.all_pos)>self.schroll_pts:
			self.plot_time_tt[:-1] = self.plot_time_tt[1:]  # shift data in the array one sample left
			self.plot_time_tt[-1] = time_elap
			self.plot_pos_tt[:-1] = self.plot_pos_tt[1:]  # shift data in the array one sample left
			self.plot_pos_tt[-1] = pos
			self.plot_volts_tt[:-1] = self.plot_volts_tt[1:]  # shift data in the array one sample left
			self.plot_volts_tt[-1] = volt
		else:
			self.plot_time_tt.extend([ time_elap ])
			self.plot_pos_tt.extend([ pos ])
			self.plot_volts_tt.extend([ volt ])
			
		## Handle view resizing 
		def updateViews():
			## view has resized; update auxiliary views to match
			self.p2.setGeometry(self.p1.vb.sceneBoundingRect())
			#p3.setGeometry(p1.vb.sceneBoundingRect())

			## need to re-update linked axes since this was called
			## incorrectly while views had different shapes.
			## (probably this should be handled in ViewBox.resizeEvent)
			self.p2.linkedViewChanged(self.p1.vb, self.p2.XAxis)
			#p3.linkedViewChanged(p1.vb, p3.XAxis)
			
		updateViews()
		self.p1.vb.sigResized.connect(updateViews)
		self.curve4.setData(self.plot_time_tt, self.plot_volts_tt)
		self.curve5.setData(self.plot_time_tt, self.plot_pos_tt)
	
	
	def update4(self,obj):
		
		xpos, ypos, voltage, timetrace = obj
		
		self.xpos_.extend([xpos])
		self.ypos_.extend([ypos])
		self.voltage_.extend([voltage])
		self.timetrace_.extend([timetrace])
		
		if self.write2db_check:
			# Save to a database file
			self.db.execute(''.join(["INSERT INTO scan VALUES (",str(xpos),",",str(ypos),",",str(voltage),",",str(timetrace),")"]))
			# Save (commit) the changes
			self.conn.commit()
		
		#################################################
		
		if self.write2mat_check:
			# save to a MATLAB file
			self.matdata['xpos']=self.xpos_
			self.matdata['ypos']=self.ypos_
			self.matdata['voltage']=self.voltage_
			self.matdata['timetrace']=self.timetrace_
		
		#################################################
		
		if self.write2txt_check:
			# get the last voltage value and save to a file
			with open(self.textfile, 'a') as thefile:
				thefile.write('%s\t\t' %xpos)
				thefile.write('%s\t\t' %ypos)
				thefile.write('%s\t\t' %voltage)
				thefile.write('%s\n' %timetrace)
		
		#################################################
		
		# Update curve3 in different plot
		if len(self.all_pos)>self.schroll_pts:
			self.acc_time_endpoint[:-1] = self.acc_time_endpoint[1:]  # shift data in the array one sample left
			self.acc_time_endpoint[-1] = timetrace
			self.acc_volt_endpoint[:-1] = self.acc_volt_endpoint[1:]  # shift data in the array one sample left
			self.acc_volt_endpoint[-1] = voltage
		else:
			self.acc_time_endpoint.extend([ timetrace ])
			self.acc_volt_endpoint.extend([ voltage ])
			
		self.curve3.setData(self.acc_time_endpoint,self.acc_volt_endpoint)
	
	
	def abort(self):

		self.worker.abort()
		
		
	def clear_vars_graphs(self):
		
		# PLOT 1 initial canvas settings
		self.all_pos=[]
		self.all_volt_endpts=[]
		self.acc_x_pos=[]
		self.acc_y_pos=[]
		self.curve1.clear()
		self.curve2.clear()
		
		# PLOT 2 initial canvas settings
		self.curve6.clear()
		
		# PLOT 5 initial canvas settings
		self.curve7.clear()
		self.curve8.clear()
		
		# PLOT 6 initial canvas settings
		self.curve9.clear()
		self.curve10.clear()
		
		# PLOT 3 initial canvas settings
		self.plot_time_tt=[]
		self.plot_volts_tt=[]
		self.plot_pos_tt=[]
		self.acc_time_endpoint=[]
		self.acc_volt_endpoint=[]
		self.xpos_=[]
		self.ypos_=[]
		self.voltage_=[]
		self.timetrace_=[]
		self.matdata={}
		
		# create plot and add it to the figure canvas
		self.curve3.clear()
		self.curve4.clear()
		self.curve5.clear()
		
	
	def bool_(self,txt):
		
		if txt=="True":
			return True
		elif txt=="False":
			return False
		
		
	def load_(self):
		
		# Initial read of the config file
		self.config = configparser.ConfigParser()
		
		try:
			self.config.read(''.join([self.cwd,os.sep,"config.ini"]))
			self.last_used_scan = self.config.get("LastScan","last_used_scan")
			
			# Initial read of the config file
			self.op_mode = self.config.get(self.last_used_scan,'op_mode')
			self.scan_mode = self.config.get(self.last_used_scan,'scan_mode')
			self.xscan = self.config.get(self.last_used_scan,'x_scan_mm').strip().split(',')
			self.yscan = self.config.get(self.last_used_scan,'y_scan_mm').strip().split(',')
			self.absrel_mm = self.config.get(self.last_used_scan,'absrel_mm').strip().split(',')
			self.dwell_time = self.config.get(self.last_used_scan,'wait_time')
			self.reset_mode = self.config.get(self.last_used_scan,'reset_mode')
			self.xy_limiter_mm = self.config.get(self.last_used_scan,'xy_limiter_mm').strip().split(',')
			self.smartscan_check = self.bool_(self.config.get(self.last_used_scan,'smart_scan'))
			self.lockin_volt = float(self.config.get(self.last_used_scan,'lockin_volt'))
			self.lockin_freq = float(self.config.get(self.last_used_scan,'lockin_freq'))
			self.schroll_pts = int(self.config.get(self.last_used_scan,'schroll_pts'))
			
			self.write2txt_str=self.config.get(self.last_used_scan,'write2txt').strip().split(',')[0]
			self.write2txt_check=self.bool_(self.config.get(self.last_used_scan,'write2txt').strip().split(',')[1])
			self.write2db_str=self.config.get(self.last_used_scan,'write2db').strip().split(',')[0]
			self.write2db_check=self.bool_(self.config.get(self.last_used_scan,'write2db').strip().split(',')[1])
			self.write2mat_str=self.config.get(self.last_used_scan,'write2mat').strip().split(',')[0]
			self.write2mat_check=self.bool_(self.config.get(self.last_used_scan,'write2mat').strip().split(',')[1])
			self.timestr = self.config.get(self.last_used_scan,'timestr')
			
			self.it6d_ca2port_str = self.config.get('Instruments','it6d_ca2port')
			self.sr810port_str = self.config.get('Instruments','sr810port')
		except configparser.NoOptionError as nov:
			QMessageBox.critical(self, 'Message',''.join(["Main FAULT while reading the config.ini file\n",str(nov)]))
			return
		
		
	def save_(self):
		
		self.timestr=time.strftime("%y%m%d-%H%M")
		self.lcd_time.display(self.timestr)
		
		self.config.read(''.join([self.cwd,os.sep,"config.ini"]))
		self.last_used_scan = self.config.get("LastScan","last_used_scan")
		
		self.config.set(self.last_used_scan,'op_mode',self.op_mode)
		self.config.set(self.last_used_scan,'scan_mode',self.scan_mode)
		self.config.set(self.last_used_scan,'x_scan_mm',','.join([str(self.xscanEdit[i].text()) for i in range(3)]))
		self.config.set(self.last_used_scan,'y_scan_mm',','.join([str(self.yscanEdit[i].text()) for i in range(3)]))
		self.config.set(self.last_used_scan,'absrel_mm',','.join([str(self.absrelEdit[ii].text()) for ii in range(2)]) )
		self.config.set(self.last_used_scan,'wait_time',str(self.dwelltimeEdit.text()))
		self.config.set(self.last_used_scan,'reset_mode',self.reset_mode)
		self.config.set(self.last_used_scan,'xy_limiter_mm',','.join([str(self.xy_limiterEdit[ii].text()) for ii in range(2)]) )
		self.config.set(self.last_used_scan,'smart_scan',str(self.cb_smartscan.isChecked()))
		self.config.set(self.last_used_scan,'lockin_volt',str(self.lockin_volt))
		self.config.set(self.last_used_scan,'lockin_freq',str(self.lockin_freq))
		self.config.set(self.last_used_scan,'schroll_pts',str(self.schroll_pts))
		self.config.set(self.last_used_scan,'timestr',self.timestr)
		
		self.config.set('Instruments','it6d_ca2port',self.it6d_ca2port_str)
		self.config.set('Instruments','sr810port',self.sr810port_str)
		
		with open(''.join([self.cwd,os.sep,"config.ini"]), 'w') as configfile:
			self.config.write(configfile)
		
		
	def finished(self):
		
		if self.write2db_check:
			for row in self.db.execute('SELECT voltage, xpos FROM scan WHERE timetrace>? ORDER BY timetrace DESC', (10,)):
				print(row)
			print('\r')
			
			for row in self.db.execute('SELECT voltage, timetrace FROM scan WHERE timetrace BETWEEN ? AND ? AND xpos<? ORDER BY timetrace DESC', (5,15,0.1)):
				print(row)
			print('\r')
			
			for row in self.db.execute('SELECT * FROM scan'):
				print(row)
			
			# We can also close the connection if we are done with it.
			# Just be sure any changes have been committed or they will be lost.
			self.conn.close()
		
		if self.write2mat_check:
			
			io.savemat(self.matfile, self.matdata)
			#print(scipy.io.loadmat(self.matfile).keys()) 
			#b = scipy.io.loadmat(self.matfile)
			#print(b['wavelength'])
		
		if self.emailset_str[1]=="yes":
			self.send_notif()
		if self.emailset_str[2]=="yes":
			self.send_data()
		
		self.isRunning = False
		self.onActivated4(self.op_mode)
		self.disconMode.setEnabled(True)
		self.write2file.setEnabled(True)
		
		self.timer.start(1000*60*5)
		plt.show()
		
		
	def warning(self, mystr):
		QMessageBox.warning(self, 'Message', mystr)
		
		
	def critical(self, mystr):
		QMessageBox.critical(self, "Message", mystr)
		
		
	def send_notif(self):
		
		self.md = Indicator_dialog.Indicator_dialog(self, "...sending notification...", "indicators/ajax-loader-ball.gif")
		
		contents=["The scan is done. Please visit the experiment site and make sure that all light sources are switched off."]
		subject="The scan is done"
		
		obj = type("obj",(object,),{"subject":subject, "contents":contents, "settings":self.emailset_str, "receivers":self.emailrec_str})
		worker=Email_Worker(obj)
		
		worker.signals.warning.connect(self.warning)
		worker.signals.critical.connect(self.critical)
		worker.signals.finished.connect(self.finished1)
		
		# Execute
		self.threadpool.start(worker)
		
		
	def finished1(self):
		self.md.close_()
		
		
	def send_data(self):
		
		self.md = Indicator_dialog.Indicator_dialog(self, "...sending files...", "indicators/ajax-loader-ball.gif")
		
		contents=["The scan is  done and the logged data is attached to this email. Please visit the experiment site and make sure that all light sources are switched off.", self.data_compexpro, self.data_pm100usb]
		subject="The scan data from the latest scan!"
		
		if self.write2txt_check:
			contents.extend([self.textfile])
		if self.write2db_check:
			contents.extend([self.dbfile])
		if self.write2mat_check:
			contents.extend([self.matfile])
		
		obj = type("obj",(object,),{"subject":subject, "contents":contents, "settings":self.emailset_str, "receivers":self.emailrec_str})
		worker=Email_Worker(obj)
		
		worker.signals.warning.connect(self.warning)
		worker.signals.critical.connect(self.critical)
		worker.signals.finished.connect(self.finished1)
		
		# Execute
		self.threadpool.start(worker)
		
		
	def closeEvent(self, event):
		
		reply = QMessageBox.question(self, 'Message', "Quit now? Any changes that are not saved will stay unsaved!", QMessageBox.Yes | QMessageBox.No)
		if reply == QMessageBox.Yes:
			if hasattr(self, 'sr810'):
				if self.conMode.isEnabled()==False:
					if not hasattr(self, 'worker'):
						self.sr810.close()
						event.accept()
					else:
						if self.isRunning:
							QMessageBox.warning(self, 'Message', "Run in progress. Stop the run then quit!")
							event.ignore()
						else:
							self.sr810.close()
							event.accept()
				else:
					pass
				
			if hasattr(self, 'timer'):
				if self.timer.isActive():
					self.timer.stop()
			
			else:
				event.accept()
		else:
		  event.ignore() 
		  
	##########################################
	
	def save_plots(self):
		
		if self.write2txt_check:
			save_to_file=''.join([self.create_file(self.write2txt_str),'.png'])
		elif self.write2db_check:
			save_to_file=''.join([self.create_file(self.write2db_str),'.png'])	
		elif self.write2mat_check:
			save_to_file=''.join([self.create_file(self.write2mat_str),'.png'])	
		else:
			save_to_file=''.join([self.create_file('data_plot_'),'.png'])	
		
		# create an exporter instance, as an argument give it
		# the item you wish to export
		exporter = pg.exporters.ImageExporter(self.p0)
		# Correction of the BUG in ImageExporter 
		# https://github.com/pyqtgraph/pyqtgraph/issues/538
		#I use the following contruct to circumvent the problem:
		exporter.params.param('width').setValue(1920, blockSignal=exporter.widthChanged)
		exporter.params.param('height').setValue(1080, blockSignal=exporter.heightChanged)
		# set export parameters if needed
		#exporter.parameters()['width'] = 100   # (note this also affects height parameter)
		# save to file
		exporter.export(save_to_file)
		
		
#########################################
#########################################
#########################################

def main():
	
	app = QApplication(sys.argv)
	ex = Run_IT6D_CA2()
	#sys.exit(app.exec())

	# avoid message 'Segmentation fault (core dumped)' with app.deleteLater()
	app.exec()
	app.deleteLater()
	sys.exit()
	
	
if __name__ == '__main__':
  
  main()
