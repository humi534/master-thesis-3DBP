from app import db,Config, Box, ExtremePoint, ExtremePointsManager
from constants import Axis, Rotation_type
from Coordinates import Coordinates
import requests
import random
import time
import copy

class Packer:

    def __init__(self, config_id, pre_determined_order=None) -> None:

        self.config = Config.query.get(config_id)
        self.sorted_by = db.session.query(Config).filter_by(id=self.config.id).first().sorting_algorithm
        self.current_height = 0

        # init extreme points in the extreme points manager
        self.extremePointsManager = ExtremePointsManager()
        extreme_points = db.session.query(ExtremePoint).filter_by(config_id=self.config.id).all()
        for extreme_point in extreme_points:
            self.extremePointsManager.add(extreme_point)
        
        #Move unfit boxes to undetermined to include them in the algorithm
        # unfitBoxes = db.session.query(Box).filter_by(status="unfit", config_id=self.config.id).all()
        # for box in unfitBoxes:
        #     box.status = "undetermined"
        #     print("___________________________________________")

        db.session.commit()
        
        if pre_determined_order is None:
            self.undeterminedBoxes= db.session.query(Box).filter_by(status="undetermined", config_id=self.config.id).all()
        else: 
            self.undeterminedBoxes = pre_determined_order
        self.placedAndUnplacedBoxes= db.session.query(Box).filter_by(status="placed", config_id=self.config.id).all()
        self.placedAndUnplacedBoxes.extend(db.session.query(Box).filter_by(status="unplaced", config_id=self.config.id).all())
        

    def set_box_direction(self):
        """à modifier en fonction de la palette"""
        for b in self.undeterminedBoxes:
            b.set_direction(Axis.width, Axis.depth, Axis.height)
    
    def sort_boxes(self):

        if self.sorted_by == "volume":
            self.undeterminedBoxes.sort(key=lambda box: box.get_volume(),reverse=True)
            
        elif self.sorted_by == "biggest_surface":
            self.undeterminedBoxes.sort(key=lambda box: box.get_biggest_surface(), reverse=True)

        elif self.sorted_by == "random":
            random.shuffle(self.undeterminedBoxes)

        else: 
            raise Exception("sorted_by variable not valid")

    def rectangle_overlap(self, box1:Box, box2:Box, axis1:int, axis2:int) -> bool:
        
        dim1 = box1.get_dimensions()
        dim2 = box2.get_dimensions()
        
        pos1 = [box1.end_x, box1.end_y, box1.end_z]
        pos2 = [box2.end_x, box2.end_y, box2.end_z]
        
        if(((pos1[axis1]+dim1[axis1])<=pos2[axis1]) or ((pos2[axis1]+dim2[axis1])<=pos1[axis1]) or ((pos1[axis2]+dim1[axis2])<=pos2[axis2]) or ((pos2[axis2]+dim2[axis2])<=pos1[axis2])):
            return False
        else:
            return True
        
    def overlap(self, box1:Box, box2:Box) -> bool:
        """Return True if box1 and box2 overlap (intersect) eachother, False otherwise"""
        return (self.rectangle_overlap(box1, box2, Axis.width, Axis.depth) 
                and self.rectangle_overlap(box1, box2, Axis.width, Axis.height) 
                and self.rectangle_overlap(box1, box2, Axis.height, Axis.depth))
    
    def get_highest_point_below(self, coord: Coordinates):
        """Renvoie un Point correspondant au point le plus haut situé juste en dessous du point mis en paramètre
            Si pas de boite, renvoie un point à hauteur de la palette"""
        possible_boxes = []

        for placedOrUnplacedBox in self.placedAndUnplacedBoxes:
            if (placedOrUnplacedBox.end_x <= coord.x < placedOrUnplacedBox.end_x + placedOrUnplacedBox.width and placedOrUnplacedBox.end_z <= coord.z < placedOrUnplacedBox.end_z + placedOrUnplacedBox.depth and placedOrUnplacedBox.end_y + placedOrUnplacedBox.height <= coord.y):
                possible_boxes.append(placedOrUnplacedBox)
        
        if not possible_boxes:
            return Coordinates(coord.x, self.config.y, coord.z)
        
        highest_box = possible_boxes[0]
        for box in possible_boxes:
            if box.end_y > highest_box.end_y and box.end_y <= coord.y and box.end_y > highest_box.end_y:
                highest_box = box
            
        return Coordinates(coord.x, highest_box.end_y+highest_box.height, coord.z)


    def box_fit(self, box:Box, extremePoint:ExtremePoint) -> bool:
        box.set_end_position(extremePoint.x, extremePoint.y, extremePoint.z)
        #check intersection with already placed boxes
        for other_box in self.placedAndUnplacedBoxes:
            if self.overlap(box, other_box):
                return False
            
        #check limits of pallet
        if box.end_x + box.width > self.config.x + self.config.width_pallet or box.end_y + box.height > self.config.y + self.config.max_height_pallet or box.end_z + box.depth > self.config.z + self.config.depth_pallet:
            return False
            
        #check stability
        stability = self.check_box_stability(box)
        if not stability:
            return False
            
        return True

    def check_extreme_point_validity(self, extreme_point:Coordinates) -> bool:
        """Check if the pivot point is not sitting on an empty space (standing in the air)"""

        if not extreme_point:
            raise Exception("pas de extreme point alors qu'il en faudrait un")

        highest_point_below = self.get_highest_point_below(extreme_point)
        
        if (highest_point_below.y != extreme_point.y):
            return False
        
        return True
        
    def check_box_stability(self, box:Box) -> bool:
        """Assuming the box sit on another box"""
        center = Coordinates(box.end_x+box.width/2, box.end_y, box.end_z+box.depth/2)
        corner1 = Coordinates(center.x+box.width/2, box.end_y, center.z+box.depth/2)
        corner2 = Coordinates(center.x-box.width/2, box.end_y, center.z+box.depth/2)
        corner3 = Coordinates(center.x+box.width/2, box.end_y, center.z-box.depth/2)
        corner4 = Coordinates(center.x-box.width/2, box.end_y, center.z-box.depth/2)
        intercorner1 = Coordinates(center.x+box.width/4, box.end_y, center.z+box.depth/4)
        intercorner2 = Coordinates(center.x-box.width/4, box.end_y, center.z+box.depth/4)
        intercorner3 = Coordinates(center.x+box.width/4, box.end_y, center.z-box.depth/4)
        intercorner4 = Coordinates(center.x-box.width/4, box.end_y, center.z-box.depth/4)
        
        highest_point_below_center = self.get_highest_point_below(center)
        highest_point_below_corner1 = self.get_highest_point_below(corner1)
        highest_point_below_corner2 = self.get_highest_point_below(corner2)
        highest_point_below_corner3 = self.get_highest_point_below(corner3)
        highest_point_below_corner4 = self.get_highest_point_below(corner4)
        highest_point_below_intercorner1 = self.get_highest_point_below(intercorner1)
        highest_point_below_intercorner2 = self.get_highest_point_below(intercorner2)
        highest_point_below_intercorner3 = self.get_highest_point_below(intercorner3)
        highest_point_below_intercorner4 = self.get_highest_point_below(intercorner4)

        nb_stable_points = 0
        if highest_point_below_center.y < box.end_y:
            nb_stable_points += 1
        
        if highest_point_below_corner1.y < box.end_y: 
            nb_stable_points += 1

        if highest_point_below_corner2.y < box.end_y:
            nb_stable_points += 1

        if highest_point_below_corner3.y < box.end_y:
            nb_stable_points += 1

        if highest_point_below_corner4.y < box.end_y:
            nb_stable_points += 1

        if highest_point_below_intercorner1.y < box.end_y:
            nb_stable_points += 1

        if highest_point_below_intercorner2.y < box.end_y:
            nb_stable_points += 1

        if highest_point_below_intercorner3.y < box.end_y:
            nb_stable_points += 1

        if highest_point_below_intercorner4.y < box.end_y:
            nb_stable_points += 1
        
        if nb_stable_points > 3:
            return False

        return True

    def pack_boxes(self):
        #self.sort_boxes()

        # box_rotations = []
        # for box in self.undeterminedBoxes:
        #     box_rotations.append(box.rotation_type)
        # print('box rotations before: ' + str(box_rotations))

        self.set_box_direction()

        # box_rotations = []
        # for box in self.undeterminedBoxes:
        #     box_rotations.append(box.rotation_type)
        # print('box rotations after: ' + str(box_rotations))
        
        # print("apres le sort et le set direction")

        while (not self.extremePointsManager.is_empty() and self.undeterminedBoxes): #tant qu'il reste des pivots et des boites non placées

            extreme_point = self.extremePointsManager.get_first_extreme_point()

            #print("Test sur le pivot: " + str(extreme_point.x) + "-" + str(extreme_point.y) + "-" + str(extreme_point.z) + " at time: " + str(time.time()))
            
            #--------pivot validity---------
            extreme_point_validity = self.check_extreme_point_validity(extreme_point) #check si le point extreme est suspendu en l'air
            if not extreme_point_validity: #si il est suspendu en l'air
                highest_point_below = self.get_highest_point_below(Coordinates(extreme_point.x, extreme_point.y, extreme_point.z))
                extreme_point.y = highest_point_below.y #projection
                db.session.commit()
            
            #print("test validity over: " + str(time.time()))

            flag = False #permet de faire un double break
            for box in self.undeterminedBoxes:
                
                for rotation_number in Rotation_type.ALL:
                    box.set_rotation_type(rotation_number)
                    #print("test box " + str(box.id) + ", rotation: " + str(rotation_number) + " at time: " + str(time.time()))
                    if self.box_fit(box, extreme_point):
                        # print("BOX FIT!! " + str(box.id) + ", rotation: " + str(rotation_number) + "at time: " + str(time.time()))
                        #box.set_position(pivot.x, pivot.y, pivot.z) #est techniquement inutile vu qu'on déplace deja la boite dans le box fit
                        self.undeterminedBoxes.remove(box)
                        self.placedAndUnplacedBoxes.append(box)
                        extreme_point_1 = ExtremePoint(x=extreme_point.x+box.width, y=extreme_point.y, z=extreme_point.z, config_id=self.config.id)
                        extreme_point_2 = ExtremePoint(x=extreme_point.x, y=extreme_point.y, z=extreme_point.z+box.depth, config_id=self.config.id)
                        extreme_point_3 = ExtremePoint(x=extreme_point.x, y=extreme_point.y+box.height, z=extreme_point.z, config_id=self.config.id)
                        
                        # db.session.add(extreme_point_1)
                        # db.session.add(extreme_point_2)
                        # db.session.add(extreme_point_3)
                        
                        self.extremePointsManager.add(extreme_point_1)
                        self.extremePointsManager.add(extreme_point_2)
                        self.extremePointsManager.add(extreme_point_3)
                        
                        #print("box placed: " + str(box.id) + " at time: " + str(time.time()))
                        box.status = "unplaced"
                        
                        flag = True
                        break
                
                if flag: #break the nested loop
                    break
            
            #si on a essayé toutes les boites dans toutes les directions et que toujours rien, supprimer le point extreme
            self.extremePointsManager.delete(extreme_point)
            # print()

        db.session.commit()

        if self.undeterminedBoxes:
            for box in self.undeterminedBoxes:
                box.status = "unfit"
                box.end_x = None
                box.end_y = None
                box.end_z = None

        db.session.commit()

        # self.extremePointsManager.clear_all(self.config.id)
        old_extreme_points = db.session.query(ExtremePoint).filter_by(config_id = self.config.id).all()
        for old_extreme_point in old_extreme_points:
            db.session.delete(old_extreme_point)
        db.session.commit()
        # print("nb placed boxes: " + str(self.config.get_nb_placed_boxes()))
        # print("nb unfit boxes: " + str(self.config.get_nb_unfit_boxes()))
        # print("filling rate: " + str(self.config.get_filling_rate()))

        # self.extremePointsManager.save_all()
        

"""
a = requests.get("http://127.0.0.1:5000/resetCurrentConfig")
b = requests.get("http://127.0.0.1:5000/setCurrentConfig")
packer = Packer(1)
print(packer.undeterminedBoxes)
packer.pack_boxes()
"""