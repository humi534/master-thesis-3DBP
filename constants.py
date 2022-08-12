# -*- coding: utf-8 -*-
"""
Created on Thu Mai 31 12:40:10 2022

@author: hugop
"""

class SortedBy:
    volume = 0
    biggest_surface = 1
    longest_edge = 2
    
    ALL = [volume, biggest_surface, longest_edge]
    
class Axis:
    width = 0
    height = 1
    depth = 2

    ALL = [width, height, depth]
    
    
class Rotation_type:
    Default = 0
    Y = 1
    X = 2
    Z = 3
    XY = 4
    XZ = 5
    
    ALL = [Default, Y, X, Z, XY, XZ]