import cv2
import numpy as np
import tkinter
import argparse
import pyautogui
import math
from timeseries import DataTimeSeries

class Vision():

	FINGER1 = 'finger1'
	FINGER2 = 'finger2'
	FINGERS = [FINGER1, FINGER2]

	def __init__(self):
		pyautogui.FAILSAFE = False
		root = tkinter.Tk()
		root.withdraw()
		self.screen_width = root.winfo_screenwidth()
		self.screen_height = root.winfo_screenheight()
		self.webcam = cv2.VideoCapture(0)
		self.cameraWidth = self.screen_width
		self.cameraHeight = self.screen_height
		self.webcam.set(cv2.CAP_PROP_FRAME_WIDTH, self.cameraWidth)
		self.webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cameraHeight)
		self.output = {}
		self.handContour = {}
		self.window = {self.FINGER1:[], self.FINGER2:[]}
		self.stationary = {self.FINGER1:False, self.FINGER2:False}
		self.foundContour = {self.FINGER1:True, self.FINGER2:True}
		self.realX = {self.FINGER1:int(self.screen_width/2), self.FINGER2:0}
		self.realY = {self.FINGER1:int(self.screen_height/2), self.FINGER2:0}
		self.stationary = False 
		self.mouseX = self.screen_width/2
		self.mouseY = self.screen_height/2
		self.queue = []
		self.dx = 0
		self.dy = 0
		self.canvas = {}
		self.clickThresh = 70
		self.clickCounter = 0
		self.pinched = False
		self.timeseries = DataTimeSeries(2, 4, auto_filter=True)
		self.window = np.zeros(4, np.float32)
		self.boundaries = {self.FINGER1:([23, 96, 50], [38, 252, 227]),
					  	   self.FINGER2:([131, 69, 0], [181, 255, 255])}

	def __read_webcam(self):
		_, self.frame = self.webcam.read()
		self.frame = cv2.flip(self.frame, 1)
		self.canvas[self.FINGER1] = np.zeros(self.frame.shape, np.uint8)
		self.canvas[self.FINGER2] = np.zeros(self.frame.shape, np.uint8)
		self.frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2HSV)

	def __add_color_threshold(self, finger):
		(lower, upper) = self.boundaries[finger]
		lower = np.array(lower, dtype="uint8")
		upper = np.array(upper, dtype="uint8")
		mask = cv2.inRange(self.frame, lower, upper)
		self.output[finger] = cv2.bitwise_and(self.frame, self.frame, mask=mask)
		self.output[finger] = cv2.cvtColor(self.output[finger], cv2.COLOR_BGR2GRAY)
	
	def __extract_contours(self, finger):
		_, self.contours, _ = cv2.findContours(self.output[finger].copy(), cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
		maxArea, idx = 0, 0
		if len(self.contours) == 0:
			self.foundContour[finger] = False
			return
		else:
			self.foundContour[finger] = True
		for i in range(len(self.contours)):
			area = cv2.contourArea(self.contours[i])
			if area > maxArea:
				maxArea = area
				idx = i
		self.realHandContour = self.contours[idx]
		self.realHandLength = cv2.arcLength(self.realHandContour, True)
		self.handContour[finger] = cv2.approxPolyDP(self.realHandContour, 0.001 * self.realHandLength,True)

	def __check_stationary(self):
		factor = 0.04
		for (x, y) in self.window:
			if (x-self.realX)**2 + (y-self.realY) > factor * min(self.cameraWidth,self.cameraHeight):
				self.stationary = False
				return
		self.stationary = True

	def __find_center(self, finger):
		self.moments = cv2.moments(self.handContour[finger])
		if self.moments["m00"] != 0:
			self.handX = int(self.moments["m10"] / self.moments["m00"])
			self.handY = int(self.moments["m01"] / self.moments["m00"])
			self.handMoment = (self.handX, self.handY)
			self.window[finger].add([self.handMoment])

	def __find_cursor_location(self, finger):
		if not self.queue:
			self.queue.append([self.realX[finger], self.realY[finger]])
			self.mouseX, self.mouseY = self.realX[finger], self.realY[finger]
			return
		if len(self.queue) == 2:
			del self.queue[0]
		self.queue.append([self.realX[finger], self.realY[finger]])
		self.dx = (self.queue[1][0] - self.queue[0][0])**2
		self.dy = (self.queue[1][1] - self.queue[0][1])**2

		self.mouseX = (self.realX[finger] / self.frame.shape[1]) * self.screen_width
		self.mouseY = (self.realY[finger] / self.frame.shape[0]) * self.screen_height
		if self.mouseX != 0 and self.mouseY != 0:
			pyautogui.moveTo(self.mouseX, self.mouseY)
		
	def __check_pinch(self):
		fingerDist = math.sqrt((self.realX[self.FINGER1] - self.realX[self.FINGER2])**2 + \
							   (self.realY[self.FINGER1] - self.realY[self.FINGER2])**2)
		print('Finger Distance: {}'.format(fingerDist))
		if fingerDist < self.clickThresh:
			if self.clickCounter > 3 and not self.pinched:
				pyautogui.click(x=self.realX[self.FINGER1], y=self.realY[self.FINGER1])
				self.pinched = True
				self.clickCounter = 0
			else:
				self.clickCounter += 1
		else:
			self.pinched = False

	def __draw(self, finger):
		if self.realX[finger] != 0 and self.realY[finger] != 0:
			cv2.circle(self.canvas[finger], (self.realX[finger], self.realY[finger]),10, (255, 0, 0), -2)
		cv2.drawContours(self.canvas[finger], [self.handContour[finger]], 0, (0, 255, 0), 1)
		# cv2.drawContours(self.canvas, [self.hullPoints], 0, (255, 0, 0), 2)

	def __frame_outputs(self, finger):
		if finger == self.FINGER1:
			cv2.imshow('Canvas: ' + finger, self.canvas[finger])
		# cv2.imshow('Output ' + finger, self.output[finger])
		# cv2.imshow('Frame', self.frame)

	def start_process(self):
		while True:
			for finger in self.FINGERS:
				self.__read_webcam()
				self.__add_color_threshold(finger)
				self.__extract_contours(finger)
				if self.foundContour[finger]:
					self.__find_center(finger)

			for finger in self.FINGERS:
				pass

			if cv2.waitKey(1) & 0xFF is ord('q'):
				break
		cv2.destroyAllWindows()

'''******************** METHODS FOR ENTIRE HAND TRACKING ********************'''

	def __get_contour_dimensions(self):
		self.minX, self.minY, self.handWidth, self.handHeight = \
			cv2.boundingRect(self.handContour)

	def __calculate_convex_hull(self):
		self.convexHull = cv2.convexHull(self.handContour,returnPoints = False)
		self.hullPoints = [self.handContour[i[0]] for i in self.convexHull]
		self.hullPoints = np.array(self.hullPoints, dtype = np.int32)
		self.defects = cv2.convexityDefects(self.handContour, self.convexHull)

	def __ecludian_space_reduction(self):
		scaleFactor = 0.3
		reducedSize = np.array(self.handContour * scaleFactor, dtype=np.int32)
		tx, ty, w, h = cv2.boundingRect(reducedSize)
		maxPoint = None
		maxRadius = 0
		for x in range(w):
			for y in range(h):
				radius = cv2.pointPolygonTest(reducedSize, (tx+x, ty+y), True)
				if radius > maxRadius:
					maxPoint =(tx+x, ty+y)
					maxRadius = radius
		realCenter = np.array(np.array(maxPoint) / scaleFactor, dtype=np.int32)
		error = int((1 / scaleFactor) * 1.5)
		maxPoint = None
		maxRadius = 0
		for x in range(realCenter[0] - error, realCenter[0] + error):
			for y in range(realCenter[1] - error, realCenter[1] + error):
				radius = cv2.pointPolygonTest(self.handContour, (x, y), True)
				if radius > maxRadius:
					maxPoint = (x,y)
					maxRadius = radius
		return np.array(maxPoint)

	def __find_palm_center(self):
		self.palmCenter = self.__ecludian_space_reduction()
		self.palmRadius = cv2.pointPolygonTest(self.handContour, tuple(self.palmCenter), True)


vision = Vision()
vision.start_process()