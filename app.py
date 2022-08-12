from datetime import timedelta
from email.mime import base
from urllib.parse import uses_params
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from flask_restful import Api, Resource, reqparse
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField
from werkzeug.utils import secure_filename
import os 
from wtforms.validators import InputRequired
from flask_sqlalchemy import SQLAlchemy
from constants import Axis, Rotation_type
import random
import numpy as np
import requests
import copy
import csv
from itertools import zip_longest




"""
Trucs à régler:
- Lorsque localIPAddress est 198. alors les bouton reset configuration et run 3D packing algorithm ne fonctionne pas car je pense qu'une requete 
n'est pas possible si le code de l'API se trouve dans le meme script. Ceci est cependant possible si l'on travaille en localhost, soit localIPAddress 
est 127.0.0.1 et que on lance le script avec flask run. C'est l'unique facon pour que l'entiereté de l'interface web fonctionne. Cependant, cela 
n'entrave en rien le code sur Hololens. Pour que celui-ci fonctionne, attention à bien mettre la variable localIPAddress à 198. Ceci semble fonctionner
car la requete se fait depuis un autre script

idee solution: mettre tout le code de l'API sur un script et tout le code de l'interface web sur un autre script. Pour que les 2 fonctionnent, 
lancer 2 invites de commandes
"""


"""
Tuto:
https://www.youtube.com/watch?v=BJThAtsZU38&ab_channel=IndonesiaMenggodong
https://www.youtube.com/watch?v=VVX7JIWx-ss&list=PLXmMXHVSvS-BlLA5beNJojJLlpE0PJgCW&index=5
"""

localIPAddress = '127.0.0.1'

app = Flask(__name__)
app.config["SECRET_KEY"] = 'hello'
app.config["UPLOAD_FOLDER"] = 'static/files'
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=10)

databaseType = "mysql+pymysql://"
username = "root:"
password = "123"
basedir = "@127.0.0.1"
dbname = "/masterthesisproject"

app.config["SQLALCHEMY_DATABASE_URI"] = databaseType + username + password + basedir + dbname
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)

class Config(db.Model):
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    sorting_algorithm = db.Column(db.String(100), nullable=False)
    current_box_id = db.Column(db.Integer)
    is_current_config = db.Column(db.Boolean, nullable=False)
    width_pallet = db.Column(db.Integer, nullable=False)
    depth_pallet = db.Column(db.Integer, nullable=False)
    max_height_pallet = db.Column(db.Integer, nullable=False)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    z = db.Column(db.Integer, nullable=False)
    boxes = db.relationship('Box', backref='config')
    extreme_points = db.relationship('ExtremePoint', backref='config')

    def __init__(self, name, sorting_algorithm, current_box_id, is_current_config, width_pallet, depth_pallet, max_height_pallet, x, y, z) -> None:
        self.name = name
        self.sorting_algorithm = sorting_algorithm
        self.current_box_id = current_box_id
        self.is_current_config = is_current_config
        self.width_pallet = width_pallet
        self.depth_pallet = depth_pallet
        self.max_height_pallet = max_height_pallet
        self.x = x
        self.y = y
        self.z = z
    
    def get_dimensions(self) -> str:
        return str(str(self.width_pallet) + "-" + str(self.depth_pallet) + "-" + str(self.max_height_pallet))

    def get_volume(self):
        return int(self.width_pallet * self.max_height_pallet * self.depth_pallet)

    def get_nb_placed_boxes(self):
        """Return the number of virtually and manually placed boxes"""
        nb_unplaced_boxes = db.session.query(Box).filter_by(config_id=self.id, status="unplaced").count()
        nb_placed_boxes = db.session.query(Box).filter_by(config_id=self.id, status="placed").count()
        return nb_unplaced_boxes + nb_placed_boxes

    def get_nb_unfit_boxes(self):
        return db.session.query(Box).filter_by(config_id=self.id, status="unfit").count()

    def get_filling_rate(self):
        unplaced_boxes = db.session.query(Box).filter_by(config_id=self.id, status="unplaced").all()
        placed_boxes = db.session.query(Box).filter_by(config_id=self.id, status="placed").all()
        boxes = unplaced_boxes + placed_boxes
        filling_amount = 0
        for box in boxes:
            filling_amount += box.get_volume()
        return filling_amount/self.get_volume()
    
class Box(db.Model):
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    depth = db.Column(db.Integer, nullable=False)
    start_x = db.Column(db.Integer, nullable=False)
    start_y = db.Column(db.Integer, nullable=False)
    start_z = db.Column(db.Integer, nullable=False)
    end_x = db.Column(db.Integer)
    end_y = db.Column(db.Integer)
    end_z = db.Column(db.Integer)
    rotation_type = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(100), nullable=False)
    config_id = db.Column(db.Integer, db.ForeignKey('config.id'))

    def __init__(self, name, width, depth, height, start_x, start_y, start_z, end_x, end_y, end_z, rotation_type, weight, status, config_id) -> None:
        self.name = name
        self.width = width
        self.depth = depth
        self.height = height
        self.start_x = start_x
        self.start_y = start_y
        self.start_z = start_z
        self.end_x = end_x
        self.end_y = end_y
        self.end_z = end_z
        self.rotation_type = rotation_type
        self.weight = weight
        self.status = status
        self.config_id = config_id

    def get_start_position(self) -> str:
        return str(str(self.start_x) + "-" + str(self.start_y) +"-"+ str(self.start_z))

    def get_end_position(self) -> str:
        return str(str(self.end_x) + "-" + str(self.end_y) +"-" +str(self.end_z))

    def set_end_position(self, x:int ,y:int ,z:int ) -> None:
        self.end_x = x
        self.end_y = y
        self.end_z = z
        # db.session.commit()

    
    def toString(self) -> str:
        return  "{ id: " + str(self.id) + ", " + "width: " + str(self.width) + ", " + "depth: " + str(self.depth) + ", " + "height: " + str(self.height) + ", " + "x: " + str(self.end_x) + ", " + "y: " + str(self.end_y)  + ", " + "z: " + str(self.end_z)  + " }"
    
    def get_volume(self) -> int:
        return int(self.width * self.height * self.depth)
    
    def get_biggest_surface(self) -> int:
        sizes = [self.width, self.depth, self.height]
        sizes.sort(reverse=True)
        return sizes[0]*sizes[1]
    
    def set_direction(self, dir1:int, dir2:int, dir3:int) -> None:
        """Oriente la boite dans l'ordre des axes donnés"""
        sizes = [self.width, self.depth, self.height]
        sizes.sort(reverse=True)
        
        #_______dir1_________
        
        if dir1 == Axis.width:
            self.width = sizes[0]
            
        elif dir1 == Axis.height:
            self.height = sizes[0]
            
        elif dir1 == Axis.depth:
            self.depth = sizes[0]
            
        #_______dir2_________
            
        if dir2 == Axis.width:
            self.width = sizes[1]
            
        elif dir2 == Axis.height:
            self.height = sizes[1]
            
        elif dir2 == Axis.depth:
            self.depth = sizes[1]
            
        #_______dir3_________
    
        if dir3 == Axis.width:
            self.width = sizes[2]
            
        elif dir3 == Axis.height:
            self.height = sizes[2]
            
        elif dir3 == Axis.depth:
            self.depth = sizes[2]
    
    def reset_rotation_type(self) -> None:
        if self.rotation_type == Rotation_type.X:
             self.height, self.depth = self.depth, self.height
        
        elif self.rotation_type == Rotation_type.Y:
            self.width, self.depth = self.depth, self.width
        
        elif self.rotation_type == Rotation_type.Z:
            self.width, self.height = self.height, self.width
            
        elif self.rotation_type == Rotation_type.XY:
            self.width, self.depth, self.height = self.depth, self.height, self.width
            
        elif self.rotation_type == Rotation_type.XZ:
            self.width, self.depth, self.height = self.height, self.width, self.depth
        
        self.rotation_type = Rotation_type.Default

        # db.session.commit()
    
    def set_rotation_type(self, rotation_type:int) -> None:
        """
            Effectue une rotation de la boite afin de la positionner à la bonne 
            rotation par rapport à sa rotation d'origine
        """
        self.reset_rotation_type()
        
        if rotation_type == Rotation_type.X:
            self.rotation_type = Rotation_type.X
            tmp = self.depth
            self.depth = self.height
            self.height = tmp
            
        elif rotation_type == Rotation_type.Y:
            self.rotation_type = Rotation_type.Y
            tmp = self.width
            self.width = self.depth
            self.depth = tmp
        
        elif rotation_type == Rotation_type.Z:
            self.rotation_type = Rotation_type.Z
            tmp = self.width
            self.width = self.height
            self.height = tmp
            
        elif rotation_type == Rotation_type.XY:
            self.rotation_type = Rotation_type.XY
            tmp = self.width
            self.width = self.height
            self.height = self.depth
            self.depth = tmp
            
        elif rotation_type == Rotation_type.XZ:
            self.rotation_type = Rotation_type.XZ
            tmp = self.width
            self.width = self.depth
            self.depth = self.height
            self.height = tmp

        # db.session.commit()
    
    def get_dimensions(self) -> list:
        return [self.width, self.height, self.depth]

class ExtremePoint(db.Model):
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    config_id = db.Column(db.Integer, db.ForeignKey('config.id'))
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    z = db.Column(db.Integer, nullable=False)

    def __init__(self, config_id, x, y, z) -> None:
        self.config_id = config_id
        self.x = x
        self.y = y
        self.z = z

class ExtremePointsManager:
    def __init__(self) -> None:
        self.extreme_points = []

    def clear_all(self, config_id):
        old_extreme_points = db.sessions.query(ExtremePoint).filter_by(config_id = config_id).all()
        for old_extreme_point in old_extreme_points:
            db.session.delete(old_extreme_point)
        db.session.commit()

    def save_all(self):
        for point in self.extreme_points:
            db.session.add(point)
        db.session.commit()

    def get_first_extreme_point(self):
        if not self.extreme_points:
            return None
        return self.extreme_points[0]

    
    def add(self, extreme_point:ExtremePoint): 
        """add the element into the list such that the order of priority is y-z-x"""
        if len(self.extreme_points)==0:
            self.extreme_points.append(extreme_point)
            return

        i = 0
        while (extreme_point.y > self.extreme_points[i].y):
            i += 1
            if i == len(self.extreme_points):
                self.extreme_points.append(extreme_point)
                return
        
        while(extreme_point.z > self.extreme_points[i].z and extreme_point.y == self.extreme_points[i].y):
            i += 1
            if i >= len(self.extreme_points):
                self.extreme_points.insert(i, extreme_point)
                return

        while(extreme_point.x > self.extreme_points[i].x and extreme_point.z == self.extreme_points[i].z and extreme_point.y == self.extreme_points[i].y):
            i += 1
            if i >= len(self.extreme_points):
                break

        self.extreme_points.insert(i, extreme_point)

    def addOld(self, extreme_point: ExtremePoint):    
        
        if len(self.extreme_points)==0:
            self.extreme_points.append(extreme_point)
            return

        i = 0
        while (extreme_point.y > self.extreme_points[i].y):
            i += 1
            if i >= len(self.extreme_points):
                self.extreme_points.append(extreme_point)
                return
        
        while(extreme_point.x < self.extreme_points[i].x and extreme_point.y == self.extreme_points[i].y):
            i += 1
            if i >= len(self.extreme_points):
                break
        
        self.extreme_points.insert(i, extreme_point)

    def delete(self, extreme_point:ExtremePoint):
        if extreme_point is None:
            raise Exception("erreur: extreme point est None")

        try:
            if extreme_point in self.extreme_points:
                
                # db.session.delete(extreme_point)
                # db.session.commit()
                self.extreme_points.remove(extreme_point)

                # print("suppression extreme point : " + str(extreme_point.x) + "-" + str(extreme_point.y) + "-" + str(extreme_point.z))
        
            else:
                raise Exception("extreme point not in ExtremePointsManager")
        
        except Exception as e:
            print(extreme_point.x)
            print(extreme_point.y)
            print(extreme_point.z)
            print(extreme_point.config_id)
            raise Exception(str(e))

    def is_empty(self):
        return (not self.extreme_points)

    def toString(self):
        s = ""
        for e in self.extreme_points:
            s += str(e.config_id)
            s += "-"
            s += str(e.id)
            s += "-"
            s += str(e.x)
            s += "-"
            s += str(e.y)
            s += "-"
            s += str(e.z)
        return s

class UploadFileForm(FlaskForm):
    file = FileField("File", validators=[InputRequired()])
    submit = SubmitField("Upload File")

class BoxGenerator:
    """
    Max size et min size sont des listes de 3 int
    Ainsi, il est possible d'exiger que toutes les boites fassent au maximum 50x50x100 par exemple. L'avantage de ce systeme
    est que l'on permet ainsi aux boites d'avoir parfois un coté plus long
    """
    def __init__(self, bin_width:int, bin_depth:int, bin_height:int, min_size:int, nb_wished_boxes:int, config_id) -> None:
        self.bin_width = bin_width
        self.bin_depth = bin_depth
        self.bin_height = bin_height
        self.min_size = min_size
        self.config_id = config_id
        self.nb_wished_boxes = nb_wished_boxes
        self.total_volume = self.bin_width*self.bin_height*self.bin_depth

        #influence la probabilité de diviser une boite en deux
        self.alpha = 1

        add_data = Box(name="#", width=self.bin_width, depth=self.bin_depth, height=self.bin_height, 
                        start_x=0, start_y=0, start_z=0,
                        end_x=0, end_y=0, end_z=0,
                        weight=1, rotation_type=0, status="unplaced", config_id=config_id )
    
        db.session.add(add_data)
        db.session.commit()

        self.boxes = [add_data]

    
    def generate_boxes(self):
        
        while len(self.boxes) < self.nb_wished_boxes: #tant qu'il reste des boites à ajouter
            
            box = self.get_next_box_to_divide()
            side = self.get_side(box)
            edge_length = self.get_edge_length(side, box)
            cut_length = self.get_cut_length(edge_length)
            self.split(side, box, cut_length)


    def get_next_box_to_divide(self) -> Box:
        percentile = random.random()
        current_ratio = 0
        for box in self.boxes:
            box_ratio = box.get_volume()/self.total_volume
            current_ratio += box_ratio
            if percentile < current_ratio:
                return box
        return box

    def get_first_box(self) -> Box:
        first_box = db.session.query(Box).filter_by(config_id=self.config_id).first()
        print()
        print("first box: " + str(first_box))
        print()
        return first_box


    
    def get_cut_length(self, edge_length):
        s=0
        max_iteration = 50
        iteration = 0
        while ((s < self.min_size or edge_length - s < self.min_size) and iteration<=max_iteration):
            #s =  int(np.random.normal(mu, sigma, 1)[0])
            s = int(np.random.uniform(edge_length/6, 5*edge_length/6))
            iteration += 1
        
        # if iteration == max_iteration:
        #     raise Exception("erreur: le nombre d'iteration est trop grand")

        return s

    

    def get_side(self, box:Box) -> str:
        #cumulative distribution function
        myDict = {}
        myDict[1] = {"length":box.width, "side":"width"}
        myDict[2] = {"length":box.depth, "side":"depth"}
        myDict[3] = {"length":box.height, "side":"height"}

        sides = [myDict[1], myDict[2], myDict[3]]
        sides.sort(key=lambda x: x["length"],reverse=True)
        total_length = 0
        for i in sides:
            total_length += i["length"]

        ratios = [sides[0]["length"]/total_length, sides[1]["length"]/total_length, sides[2]["length"]/total_length]
        percentile = random.random()
        current_total = 0
        for i, ratio in enumerate(ratios):
            current_total += ratio
            if percentile < current_total:
                break
        return sides[i]["side"]

        """
        sides = ["width", "depth","height"]
        return random.choice(sides)
        """

    def get_edge_length(self, side:str, box:Box):
        sides = ["width", "height","depth"]
        if side not in sides:
            raise Exception ("side doit etre compris dans ['width', 'height', 'depth']")
        if side == "width":
            return box.width
        elif side == "height":
            return box.height
        elif side == "depth":
            return box.depth

    def split(self, side:str, box:Box, cut_length):
        """
        side doit etre compris entre ["width", "height", "depth"]
        cut_length est la distance allant du point de coordonnées de la boites jusqu'à l'endroit de découpe
        """

        sides = ["width", "height","depth"]
        if side not in sides:
            raise Exception ("side doit etre compris dans ['width', 'height', 'depth']")

        #on coupe verticallement en face de soi
        if side == "width":
            sub_box1 = Box(name="#", width=cut_length, depth=box.depth, height=box.height, start_x=0, start_y=0, start_z=0, 
                            end_x=box.end_x, end_y=box.end_y, end_z=box.end_z, rotation_type=0, status=box.status, config_id=box.config_id, weight=1)
    
            sub_box2 = Box(name="#", width=box.width-cut_length, depth=box.depth, height=box.height, start_x=0, start_y=0, start_z=0, 
                            end_x=box.end_x+cut_length, end_y=box.end_y, end_z=box.end_z, rotation_type=0, status=box.status, config_id=box.config_id, weight=1)

        #on coupe verticallement perpendiculairement à notre vue
        elif side == "depth":
            sub_box1 = Box(name="#", width=box.width, depth=cut_length, height=box.height, start_x=0, start_y=0, start_z=0, 
                            end_x=box.end_x, end_y=box.end_y, end_z=box.end_z, rotation_type=0, status=box.status, config_id=box.config_id, weight=1)
    
            sub_box2 = Box(name="#", width=box.width, depth=box.depth-cut_length, height=box.height, start_x=0, start_y=0, start_z=0, 
                            end_x=box.end_x, end_y=box.end_y, end_z=box.end_z+cut_length, rotation_type=0, status=box.status, config_id=box.config_id, weight=1)

        #on coupe horizontallement la boite
        elif side == "height":
            sub_box1 = Box(name="#", width=box.width, depth=box.depth, height=cut_length, start_x=0, start_y=0, start_z=0, 
                            end_x=box.end_x, end_y=box.end_y, end_z=box.end_z, rotation_type=0, status=box.status, config_id=box.config_id, weight=1)
    
            sub_box2 = Box(name="#", width=box.width, depth=box.depth, height=box.height-cut_length, start_x=0, start_y=0, start_z=0, 
                            end_x=box.end_x, end_y=box.end_y+cut_length, end_z=box.end_z, rotation_type=0, status=box.status, config_id=box.config_id, weight=1)

        db.session.delete(box)
        db.session.add(sub_box1)
        db.session.add(sub_box2)
        db.session.commit()

        self.boxes.remove(box)
        self.boxes.append(sub_box1)
        self.boxes.append(sub_box2)
        self.boxes.sort(key=lambda box: box.get_volume(),reverse=True)

    def set_all_box_to_unplaced(self):
        boxes = db.session.query(Box).filter_by(config_id=self.config_id).all()
        for box in boxes:
            box.status = "unplaced"
        
        db.session.commit()


@app.route("/")
@app.route("/index", methods=["GET","POST"])
def index():
    """
    form = UploadFileForm()
    if form.validate_on_submit():
        file = form.file.data
        file.save(os.path.join(os.path.abspath(os.path.dirname(__file__)), app.config['UPLOAD_FOLDER'], secure_filename(file.filename)))
        return "File has been uploaded"
    return render_template("index.html", form=form)
    """
    all_configs = db.session.query(Config)
    nb_boxes = [db.session.query(Box).filter_by(config_id=config.id).count() for config in all_configs]
    return render_template('index.html', data=all_configs, nb_boxes=nb_boxes)

@app.route("/edit_config/<int:config_id>", methods=["GET", "POST"])
def edit_config(config_id):
    config = Config.query.get(config_id)
    return render_template('edit_config.html', config=config)

@app.route("/input_config", methods=["GET", "POST"])
def input_config():
    return render_template('input_config.html')

@app.route("/config_to_box/<int:config_id>", methods=["GET", "POST"])
@app.route("/config_to_box", methods=["GET", "POST"])
def config_to_box(config_id=None):

    #mode add new config
    if config_id == None:
        if request.method == 'POST':
            name = request.form['name']
            width_pallet = request.form['width_pallet']
            depth_pallet = request.form['depth_pallet']
            max_height_pallet = request.form['max_height_pallet']
            sorting_algorithm = request.form['sorting_algorithm']
            is_new_current_config = request.form.get('is_new_current_config')

            if is_new_current_config:
                try:
                    #undo previous current config
                    current_config_id = db.session.query(Config).filter_by(is_current_config=True).first().id
                    current_config = Config.query.get(current_config_id)
                    current_config.is_current_config = False
                except:
                    pass

                is_new_current_config = True
            else:
                is_new_current_config = False

            add_data = Config(name=name, 
                                width_pallet=width_pallet, 
                                depth_pallet=depth_pallet, 
                                max_height_pallet=max_height_pallet, 
                                sorting_algorithm=sorting_algorithm,
                                is_current_config=is_new_current_config,
                                current_box_id=None,
                                x=0,
                                y=0,
                                z=0
                                )
            db.session.add(add_data)
            db.session.commit()
        return redirect(url_for('input_box', config_id=add_data.id))

    #mode edit
    else:
        if request.method == 'POST':
            config = Config.query.get(config_id)
            config.name = request.form['name']
            config.width_pallet = request.form['width_pallet']
            config.depth_pallet = request.form['depth_pallet']
            config.max_height_pallet = request.form['max_height_pallet']
            config.sorting_algorithm = request.form['sorting_algorithm']

        db.session.commit()
        return redirect(url_for('input_box', config_id=config_id))

@app.route("/input_box/<int:config_id>", methods=["GET", "POST"])
def input_box(config_id):
    boxes = db.session.query(Box).filter_by(config_id=config_id)
    return render_template('input_box.html', boxes=boxes, config_id=config_id)

@app.route('/set_current_config/<int:id>')
def set_current_config(id):
    try:
        current_config_id = db.session.query(Config).filter_by(is_current_config=True).first().id
        if id != current_config_id:
            #unset previous current config
            current_config = Config.query.get(current_config_id)
            current_config.is_current_config = False

            #set new current config
            new_current_config = Config.query.get(id)
            new_current_config.is_current_config = True
            db.session.commit()
        return redirect(url_for('index'))
        
    except:
        #set new current config
        new_current_config = Config.query.get(id)
        new_current_config.is_current_config = True
        db.session.commit()
        return redirect(url_for('index'))

@app.route('/delete_config/<int:config_id>')
def delete_config(config_id):
    config = Config.query.get(config_id)
    db.session.delete(config)
    db.session.commit()
    flash('Delete Data Success')
    return redirect(url_for('index'))

@app.route('/delete_box/<int:box_id>/<int:config_id>')
def delete_box(box_id, config_id):
    box = Box.query.get(box_id)
    db.session.delete(box)
    db.session.commit()
    return redirect(url_for('input_box', config_id=config_id))

@app.route('/add_box/<int:config_id>', methods=["GET", "POST"])
def add_box(config_id):
    name = request.form['name']
    width = request.form['width']
    depth = request.form['depth']
    height = request.form['height']
    start_x = request.form['start_x']
    start_y = request.form['start_y']
    start_z = request.form['start_z']
    weight = request.form['weight']

    add_data = Box(name=name, 
                    width=width, 
                    depth=depth, 
                    height=height, 
                    start_x=start_x,
                    start_y=start_y,
                    start_z=start_z,
                    end_x=None,
                    end_y=None,
                    end_z=None,
                    weight=weight,
                    rotation_type=0,
                    status="undetermined",
                    config_id=config_id
                    )
    
    db.session.add(add_data)
    db.session.commit()
    return redirect(url_for('input_box', config_id=config_id))

@app.route('/generate_boxes/<int:config_id>', methods=["GET", "POST"])
def generate_boxes(config_id):
    return render_template('input_generate_boxes.html', config_id=config_id)

@app.route('/boxes_to_run_algo/<int:config_id>', methods=["GET", "POST"])
def boxes_to_run_algo(config_id):
    return render_template('input_run_algo.html', config_id=config_id)

@app.route('/generate_to_box/<int:config_id>', methods=["GET", "POST"])
def generate_to_box(config_id):
    
    config = Config.query.get(config_id)

    if request.method == 'POST':
        min_size = int(request.form['min_size'])
        nb_wished_boxes = int(request.form['nb_whished_boxes'])
    
        config = Config.query.get(config_id)
        boxGen = BoxGenerator(bin_width=config.width_pallet, 
                            bin_depth=config.depth_pallet, 
                            bin_height=config.max_height_pallet,
                            min_size=min_size,
                            nb_wished_boxes=nb_wished_boxes,
                            config_id=config_id
                            )
        boxGen.generate_boxes()

        return redirect(url_for('input_box', config_id=config_id))

    raise Exception("Not supposed to arrive here")

@app.route('/reset_configuration/<int:config_id>', methods=["GET", "POST"])
def reset_configuration(config_id):
    current_config_id = db.session.query(Config).filter_by(is_current_config=True).first().id
    if config_id != current_config_id:
        #unset previous current config
        current_config = Config.query.get(current_config_id)
        current_config.is_current_config = False

        #set new current config
        new_current_config = Config.query.get(config_id)
        new_current_config.is_current_config = True
        db.session.commit()

    s = "http://" + str(localIPAddress) + ":5000/resetCurrentConfig"
    print()
    print(s)
    print()
    # requests.get("http://192.168.1.51:5000/resetCurrentConfig")
    # requests.get("http://127.0.0.1:5000/resetCurrentConfig")
    requests.get(s)
    return redirect(url_for('input_box', config_id=config_id))

@app.route('/reset_status/<int:config_id>', methods=["GET", "POST"])
def reset_status(config_id):
    boxes = db.session.query(Box).filter_by(config_id=config_id, status='placed').all()
    for box in boxes:
        box.status = 'unplaced'
    db.session.commit()
    return redirect(url_for('input_box', config_id=config_id))

@app.route('/run_algorithm/<int:config_id>', methods=["GET", "POST"])
def run_algorithm(config_id):
    current_config_id = db.session.query(Config).filter_by(is_current_config=True).first().id

    if request.method == 'POST':
        nb_iterations = int(request.form['nb_iterations'])

    if config_id != current_config_id:
        #unset previous current config
        current_config = Config.query.get(current_config_id)
        current_config.is_current_config = False

        #set new current config
        new_current_config = Config.query.get(config_id)
        new_current_config.is_current_config = True
        db.session.commit()

    s = "http://" + str(localIPAddress) + ":5000/setCurrentConfig?nb_iterations=" + str(nb_iterations)
    print('request: ' + str(s))
    requests.get(s)
    return redirect(url_for('input_box', config_id=config_id))

@app.route('/report/<int:config_id>', methods=["GET", "POST"])
def report(config_id):
    config = Config.query.get(config_id)
    data = {}
    data["score"] = str(round(config.get_filling_rate()*100, 2)) + '%'
    data["volume"] = config.get_volume()
    data["nb_unfit_boxes"] = config.get_nb_unfit_boxes()
    data["nb_placed_boxes"] = config.get_nb_placed_boxes() #manually and virtually placed boxes
    data["sorting_algorithm"] = config.sorting_algorithm
    data["dimensions"] = config.get_dimensions()
    data["name"] = config.name
    return render_template('report.html', config_id=config_id, data=data)

@app.route('/clear_all_boxes/<int:config_id>', methods=["GET", "POST"])
def clear_all_boxes(config_id):
    boxes = db.session.query(Box).filter_by(config_id = config_id).all()
    for box in boxes:
        db.session.delete(box)
    db.session.commit()
    return redirect(url_for('input_box', config_id=config_id))




"""
http://127.0.0.1:5000/resetCurrentConfig
http://127.0.0.1:5000/setPallet?x=0&y=0&z=0
http://127.0.0.1:5000/setCurrentConfig?nb_iterations=1
http://127.0.0.1:5000/getNextBox
http://127.0.0.1:5000/currentBoxPlaced
http://127.0.0.1:5000/boxDamaged

http://192.168.1.51:5000/resetCurrentConfig
http://192.168.1.51:5000/setPallet?x=0&y=0&z=0
http://192.168.1.51:5000/setCurrentConfig?nb_iterations=1
http://192.168.1.51:5000/getNextBox
http://192.168.1.51:5000/currentBoxPlaced

file:///C:/Users/hugop/OneDrive/Documents/master/memoire/code/3DBP/config.json
"""


api = Api(app)

    

#----------------------------------Get Next Box----------------------------------------
#envoie la boite non encore placee manuellement ayant le plus petit end_y virtuellement
class getNextBox(Resource):
    def get(self):
        print("appel de la fonction getNextBox")
        
        try:
            current_config = db.session.query(Config).filter_by(is_current_config=True).first()

            #check if there are some boxes in the config
            if db.session.query(Box).filter_by(config_id=current_config.id).count() == 0:
                return {"message":"no box in the config to set to current box"}

            if current_config.current_box_id is None:
                #get the lowest box
                lowest_box = db.session.query(Box).filter_by(config_id=current_config.id,  status="unplaced").order_by(Box.end_y.asc()).first()

                #set the lowest box to the current box id
                current_config.current_box_id = lowest_box.id
                db.session.commit()

            current_box_id = current_config.current_box_id
            box_to_send = Box.query.get(current_box_id)
            print("box id: " + str(current_box_id))
            print("width box: " + str(box_to_send.width))
            myDict = box_to_send.__dict__
            print()
            print(myDict)
            print()
            myDict.pop("_sa_instance_state")
            return myDict

        except Exception as e:
            return {"message":"erreur dans l'appel de la fonction", "error":str(e)}

api.add_resource(getNextBox, "/getNextBox")


#-----------------------------------Box Placed------------------------------------------
#en appelant cette fonction, Hololens signale que l'operateur a placé la boite qu'il avait en main
class currentBoxPlaced(Resource):
    def get(self):
        print("appel de la fonction currentBoxPlaced")
        try:
            current_config = db.session.query(Config).filter_by(is_current_config=True).first()
            current_box_id = current_config.current_box_id
            if current_box_id is None:
                return {"message":"pas de current box"}
            current_box = Box.query.get(current_box_id)
            current_box.status = "placed"
            current_config.current_box_id = None
            db.session.commit()

            nb_placed_boxes = db.session.query(Box).filter_by(config_id=current_config.id, status="placed").count()
            nb_unplaced_boxes = db.session.query(Box).filter_by(config_id=current_config.id, status="unplaced").count()
            ratio = nb_placed_boxes/(nb_placed_boxes+nb_unplaced_boxes)

            myDict = {}
            myDict["currentRatio"] = round(ratio,2)
            return myDict

        except Exception as e:
            return {"message":"erreur dans l'appel de la fonction:", "error":str(e)}
        
api.add_resource(currentBoxPlaced, "/currentBoxPlaced")


#-----------------------------------Box Damaged ---------------------------------------
import Packer
class boxDamaged(Resource):
    def get(self):
        print("appel de la fonction boxDamaged")

        current_config = db.session.query(Config).filter_by(is_current_config=True).first()
        current_box_id = current_config.current_box_id
        if current_box_id == None:
            raise Exception("pas de current box id dans l'appel de la fonction boxDamaged")

        box = db.session.query(Box).filter_by(id=current_box_id).first()
        if box == None:
            raise Exception("l'id de la current box n'est pas présent dans la db")

        box.status = "damaged"
        db.session.commit()

        undetermined_boxes = db.session.query(Box).filter_by(status="undetermined", config_id=current_config.id).all()
        manually_placed_boxes = db.session.query(Box).filter_by(status="placed", config_id=current_config.id).all()

        if current_config.sorting_algorithm == "volume":
            undetermined_boxes.sort(key=lambda box: box.get_volume(),reverse=True)
            
        elif current_config.sorting_algorithm == "biggest_surface":
            undetermined_boxes.sort(key=lambda box: box.get_biggest_surface(), reverse=True)

        elif current_config.sorting_algorithm == "random":
            random.shuffle(undetermined_boxes)

        extreme_points = db.session.query(ExtremePoint).filter_by(config_id=current_config.id).all()
        for extreme_point in extreme_points:
            db.session.delete(extreme_point)
            db.session.commit()

        for manually_placed_box in manually_placed_boxes:
            x_coord = manually_placed_box.end_x + manually_placed_box.width
            y_coord = manually_placed_box.end_y + manually_placed_box.height
            z_coord = manually_placed_box.end_z + manually_placed_box.depth
            e = ExtremePoint(config_id=current_config.id, x = x_coord, y=y_coord, z=z_coord)
            db.session.add(e)
            db.session.commit()

        
        packer = Packer.Packer(config_id=current_config.id, pre_determined_order=undetermined_boxes)
        packer.pack_boxes()
        return 200

api.add_resource(boxDamaged, "/boxDamaged")


#-----------------------------Set Pallet Position -------------------------------------
#en appelant cette fonction get, l'operateur envoie les coordonnees et dimensions de la palette
class setPallet(Resource):
    def get(self):
        print("appel de la fonction setPalletPosition")

        try:
            parser = reqparse.RequestParser()
            parser.add_argument('x', type=int, help="x of pallet is required", required = True)
            parser.add_argument('y', type=int, help="y of pallet is required", required = True)
            parser.add_argument('z', type=int, help="z of pallet is required", required = True)

            x = int(request.args.get('x'))
            y = int(request.args.get('y'))
            z = int(request.args.get('z'))

            current_config = db.session.query(Config).filter_by(is_current_config=True).first()
            current_config.x = x
            current_config.y = y
            current_config.z = z
            db.session.commit()

            return {"message": "Position of the pallet updated"}
        except Exception as e:
            return {"message": "une erreur s est produite lors de la pose de la palette", "error":str(e)}


api.add_resource(setPallet, "/setPallet")

#------------------------------Reset Current Config --------------------------------------

class resetCurrentConfig(Resource):
    def get(self):
        print("appel de la fonction resetCurrentConfig")

        try:
            current_config = db.session.query(Config).filter_by(is_current_config=True).first()

            print("config utilisée:  {}".format(current_config.id))
            current_config.current_box_id = None
            current_config.x = 0
            current_config.y = 0
            current_config.z = 0

            boxes = db.session.query(Box).filter_by(config_id=current_config.id).all()

            for box in boxes:
                box.status = "undetermined"
                box.end_x = None
                box.end_y = None
                box.end_z = None
                box.rotation_type = 0

            db.session.commit()
            return 200

        except Exception as e:
            return {"message": "erreur lors du reset", "error":str(e)}

api.add_resource(resetCurrentConfig, "/resetCurrentConfig")


#------------------------------Set Config File --------------------------------------
#permet de definir le premier pivot, ajouter les boites dans la section undefined, et appelle le packer 
class setCurrentConfig(Resource):
    
    def get(self):

        try: 
            print("appel de la fonction setCurrentConfig")
            
            # sorting_type = "volume"

            current_config = db.session.query(Config).filter_by(is_current_config=True).first()

            parser = reqparse.RequestParser()
            parser.add_argument('nb_iterations', type=int, help="the number of iterations", required = False)

            nb_iterations = int(request.args.get('nb_iterations'))


            final_log = "\n\nfinal log: "
            best_score = 0
            object_best_order = db.session.query(Box).filter_by(status="undetermined", config_id=current_config.id).all()
            best_order = []
            best_scores = []
            all_scores = []
            results = {} #key-value dictionnary containing the list of id as key and the score as result

            if current_config.sorting_algorithm == "volume":
                object_best_order.sort(key=lambda box: box.get_volume(),reverse=True)
                
            elif current_config.sorting_algorithm == "biggest_surface":
                object_best_order.sort(key=lambda box: box.get_biggest_surface(), reverse=True)

            elif current_config.sorting_algorithm == "random":
                random.shuffle(object_best_order)

            for box in object_best_order:
                best_order.append(box.id)
            best_order = best_order[::-1]
            
            for i in range(nb_iterations):
                
                pre_determined_order = copy.deepcopy(best_order)

                if i > 0: #le swap est inutile lors de la premiere itération

                    #swap elements
                    pos1 = pre_determined_order.index(random.choice(pre_determined_order))
                    pos2 = pre_determined_order.index(random.choice([x for x in pre_determined_order if x != pre_determined_order[pos1]]))
                    pre_determined_order[pos1], pre_determined_order[pos2] = pre_determined_order[pos2], pre_determined_order[pos1]

                # current_config.sorting_algorithm = sorting_type
                # db.session.commit()
                extreme_points = db.session.query(ExtremePoint).filter_by(config_id=current_config.id).all()
                for extreme_point in extreme_points:
                    db.session.delete(extreme_point)
                    db.session.commit()

                first_extreme_point = ExtremePoint(config_id=current_config.id, x=0, y=0, z=0)
                db.session.add(first_extreme_point)
                db.session.commit()

                box_list = []
                for i in pre_determined_order:
                    box_list.append(db.session.query(Box).filter_by(id=i).first())
                box_list = box_list[::-1]

                packer = Packer.Packer(config_id=current_config.id, pre_determined_order=box_list)
                packer.pack_boxes()
                # db.session.commit()

                score = current_config.get_filling_rate()
                print("score: " + str(score))

                #Reset boxes locations 
                boxes = db.session.query(Box).filter_by(config_id=current_config.id).all()
                for box in boxes:
                    box.status = "undetermined"
                    box.end_x = None
                    box.end_y = None
                    box.end_z = None
                    box.rotation_type = 0
                db.session.commit()

                results[score] = pre_determined_order

                if score > best_score:
                    best_score = copy.deepcopy(score)
                    best_order = copy.deepcopy(pre_determined_order)
                
                best_scores.append(best_score)
                all_scores.append(score)
                
                # raise Exception ("error")
                
            
            final_log += str("best scores: " + str(best_scores))
            final_log += str("all scores: " + str(all_scores))

            # Mettre le meilleur score
            extreme_points = db.session.query(ExtremePoint).filter_by(config_id=current_config.id).all()
            for extreme_point in extreme_points:
                db.session.delete(extreme_point)
                db.session.commit()

            first_extreme_point = ExtremePoint(config_id=current_config.id, x=0, y=0, z=0)
            db.session.add(first_extreme_point)
            db.session.commit()

            #Reset boxes locations
            boxes = db.session.query(Box).filter_by(config_id=current_config.id).all()
            for box in boxes:
                box.status = "undetermined"
                box.end_x = None
                box.end_y = None
                box.end_z = None
                box.rotation_type = 0
            db.session.commit()

            print()
            print("score: " + str(best_score) + str(results[best_score]))
            print()
            box_list = []
            for id_box in results[best_score]:
                box_list.append(db.session.query(Box).filter_by(id=id_box).first())
            box_list = box_list[::-1]

            packer = Packer.Packer(config_id=current_config.id, pre_determined_order=box_list)
            packer.pack_boxes()
            db.session.commit()
            
            newScore = current_config.get_filling_rate()
            print()
            print("new score: " + str(newScore))
            print()

            print("----------------------------------------------------------")
            print(final_log)
            print()
            print(results)
            print()
            print('best scores : ' + str(best_scores))


            #code utile pour inscrire les scores dans un fichier excel afin de générer des graphiques

            # d = [best_scores, all_scores]
            # export_data = zip_longest(*d, fillvalue = '')
            # with open('scoresRandom2.csv', 'w', encoding="ISO-8859-1", newline='') as myfile:
            #     wr = csv.writer(myfile)
            #     wr.writerow(("List1", "List2"))
            #     wr.writerows(export_data)
            # myfile.close()


            return 200

        except Exception as e:
            return {"message":"erreur dans l'appel de la fonction:", "error":str(e)}


api.add_resource(setCurrentConfig, "/setCurrentConfig")




#-------------------------------------Main --------------------------------------------


if __name__ == "__main__":
    app.run(host='192.168.1.51', port=5000, debug=True, threaded=False)

    # app.run(debug=True, threaded=False)
    # app.run(host='192.168.0.29', port=5000, debug=True, threaded=False)
