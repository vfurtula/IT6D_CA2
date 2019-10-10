import numpy
import matplotlib.pyplot as plt



class Myrange:
	
	def __init__(self,list_start,list_end,list_step):
		
		self.list_start=list_start
		self.list_end=list_end
		self.list_step=list_step
		
	def myrange(self):
		
		if self.list_start<self.list_end:
			return_list = numpy.arange(self.list_start,self.list_end,abs(self.list_step))
			if return_list[-1]+abs(self.list_step)<=self.list_end:
				return_list= numpy.append(return_list , [return_list[-1]+abs(self.list_step)])
			return return_list
		
		elif self.list_start>self.list_end:
			return_list = numpy.arange(self.list_start,self.list_end,-abs(self.list_step))
			if return_list[-1]-abs(self.list_step)>=self.list_end:
				return_list = numpy.append(return_list , [return_list[-1]-abs(self.list_step)])
			return return_list
	
	
	
class Scan_methods:

	def __init__(self,xgr_start,xgr_end,xgr_step,ygr_start,ygr_end,ygr_step):
		# define grids and make empty lists ready
		
		mrx=Myrange(xgr_start,xgr_end,xgr_step)
		self.xgrid = mrx.myrange() 
		
		mry=Myrange(ygr_start,ygr_end,ygr_step)
		self.ygrid = mry.myrange()

	def run(self,method):
		if method == 'xsnake':
			x,y=self.xsnake()
		elif method == 'ysnake':
			x,y=self.ysnake()
		elif method == 'xwise':
			x,y=self.xwise()
		elif method == 'ywise':
			x,y=self.ywise()
		
		return x,y
	
	
	
	def xsnake(self):
		xscan = []
		yscan = []
		# raster scan pattern along x axis
		for i,yi in enumerate(self.ygrid):
			xscan.append(self.xgrid[::(-1)**i]) # reverse when i is odd
			yscan.append(numpy.ones_like(self.xgrid)*yi)   

		# squeeze lists together to vectors
		x_scan=numpy.concatenate(xscan)
		y_scan=numpy.concatenate(yscan)
		
		return x_scan,y_scan
	
	def ysnake(self):
		xscan = []
		yscan = []
		# raster scan pattern along y axis
		for i,xi in enumerate(self.xgrid):
			yscan.append(self.ygrid[::(-1)**i]) # reverse when i is odd
			xscan.append(numpy.ones_like(self.ygrid)*xi)   

		# squeeze lists together to vectors
		x_scan=numpy.concatenate(xscan)
		y_scan=numpy.concatenate(yscan)
		
		return x_scan,y_scan
	
	def xwise(self):
		xscan = []
		yscan = []
		# raster scan pattern along x axis
		for yi in self.ygrid:
			xscan.append(self.xgrid) # reverse when i is odd
			yscan.append(numpy.ones_like(self.xgrid)*yi)   

		# squeeze lists together to vectors
		x_scan=numpy.concatenate(xscan)
		y_scan=numpy.concatenate(yscan)
		
		return x_scan,y_scan
	
	def ywise(self):
		xscan = []
		yscan = []
		# raster scan pattern along y axis
		for xi in self.xgrid:
			yscan.append(self.ygrid) # reverse when i is odd
			xscan.append(numpy.ones_like(self.ygrid)*xi)   

		# squeeze lists together to vectors
		x_scan=numpy.concatenate(xscan)
		y_scan=numpy.concatenate(yscan)
		
		return x_scan,y_scan


def test_Scan_methods():
	
	sm=Scan_methods(20,31,1,10,16,1)
	x1,y1=sm.run('xsnake')
	x2,y2=sm.run('ysnake')
	x3,y3=sm.run('xwise')
	x4,y4=sm.run('ywise')
	
	# quick plot
	plt.plot(x1, y1, '-rx')
	plt.axis([19, 32, 9, 17])
	plt.show()
	
	plt.plot(x2, y2, '-bx')
	plt.axis([19, 32, 9, 17])
	plt.show()
	
	plt.plot(x3, y3, '-ro')
	plt.axis([19, 32, 9, 17])
	plt.show()
	
	plt.plot(x4, y4, '-bo')
	plt.axis([19, 32, 9, 17])
	plt.show()
	
	
if __name__ == "__main__":
	
  test_Scan_methods()