import c4d
import os
import struct
import zipfile
import time

from c4d import bitmaps, gui, plugins, documents, utils
from xml.dom import minidom

PLUGIN_ID = 1038148
VERSION = '1.0.3'

print "- - - - - - - - - - - -"
print "           _           "
print "          [_]          "
print "       / |   | \       "
print "      () '---'  C      "
print "        |  |  |        "
print "        [=|=]          "
print "                       "
print "LDD2C4D - " + VERSION
print "- - - - - - - - - - - -"

# container ids
DATABASE = 1000
TEXTUR = 1001

# Element IDs
IDM_ABOUT = 1011
IDC_EXPORT_TEX = 1012
IDC_TEXT_DATABASE = 1013
IDC_BUTTON_DATABASE = 1014
IDC_BUTTON_LOAD = 1015
IDC_SLIDER_SCALE = 1016
IDC_TEXT_TEXTURE = 1017
IDC_TEXT_MAT_TEMPLATE = 1018
IDC_BUTTON_TEXTURE = 1019
IDC_MAT_LINK = 1020 
IDC_INSTANCES = 1021
IDC_RENDERINSTANCES = 1022

# Material types
MATERIAL_TYPE_C4D   = 5703

PRIMITIVEPATH = '/Primitives/'
GEOMETRIEPATH = PRIMITIVEPATH + 'LOD0/'
DECORATIONPATH = '/Decorations/'
MATERIALNAMESPATH = '/MaterialNames/'

FLIP = c4d.Matrix(c4d.Vector(0, 0, 0), c4d.Vector(1, 0, 0), c4d.Vector(0, 1, 0), c4d.Vector(0, 0, -1))

class Bone(object):
    def __init__(self, node):
        (a, b, c, d, e, f, g, h, i, x, y, z) = map(float, node.getAttribute('transformation').split(','))
        self.matrix = FLIP * c4d.Matrix(c4d.Vector(x, y, z), c4d.Vector(a, b, c), c4d.Vector(d, e, f), c4d.Vector(g, h, i)) 

class Part(object):
    def __init__(self, node):
        self.designID = node.getAttribute('designID')
        self.materials = map(str, node.getAttribute('materials').split(',')) 
        lastm = '0'
        for i, m in enumerate(self.materials):
            if (m == '0'):
                self.materials[i] = lastm
            else:
                lastm = m
        if node.hasAttribute('decoration'):
            self.decoration = map(str,node.getAttribute('decoration').split(','))
        self.Bones = []
        for childnode in node.childNodes:
            if childnode.nodeName == 'Bone':
                self.Bones.append(Bone(node=childnode)) 

class Brick(object):
    def __init__(self, node):
        self.designID = node.getAttribute('designID')
        self.Parts = []
        for childnode in node.childNodes:
            if childnode.nodeName == 'Part':
                self.Parts.append(Part(node=childnode))

class SceneCamera(object):
    def __init__(self, node):
        (a, b, c, d, e, f, g, h, i, x, y, z) = map(float, node.getAttribute('transformation').split(','))
        self.matrix = c4d.Matrix(c4d.Vector(x, y, z), c4d.Vector(a, b, c), c4d.Vector(d, e, f),c4d.Vector(g, h, i))
        self.fieldOfView = float(node.getAttribute('fieldOfView'))
        self.distance = float(node.getAttribute('distance'))

class Scene(object):
    def __init__(self, file):
        self.Name = ''
        self.Version = ''
        self.Bricks = []
        self.Scenecamera = None

        data = ''
        if file.endswith('.lxfml'):
            with open(file, "rb") as file:
                data = file.read()
        elif file.endswith('.lxf'):
            zf = zipfile.ZipFile(file, 'r')
            data = zf.read('IMAGE100.LXFML')
        else:
            return

        xml = minidom.parseString(data)
        self.Name = xml.firstChild.getAttribute('name')
                
        for node in xml.firstChild.childNodes: 
            if node.nodeName == 'Meta':
                for childnode in node.childNodes:
                    if childnode.nodeName == 'BrickSet':
                        self.Version = str(childnode.getAttribute('version'))
            elif node.nodeName == 'Cameras':
                for childnode in node.childNodes:
                    if childnode.nodeName == 'Camera':
                        self.Scenecamera = SceneCamera(node=childnode)
            elif node.nodeName == 'Bricks':
                for childnode in node.childNodes:
                    if childnode.nodeName == 'Brick':
                        self.Bricks.append(Brick(node=childnode))
        
        print 'Scene "'+ self.Name + '" Brickversion: ' + str(self.Version) 

class GeometrieReader(object):
    def __init__(self, data):
        self.offset = 0
        self.data = data
        self.positions = []
        self.normals = []
        self.textures = []
        self.faces = []
        self.bonemap = {}

        if self.readInt() == 1111961649:
            self.valueCount = self.readInt()
            self.indexCount = self.readInt()
            self.faceCount = self.indexCount / 3
            options = self.readInt()

            for i in range(0, self.valueCount):            
                self.positions.append(c4d.Vector(self.readFloat(), self.readFloat(), self.readFloat()))

            for i in range(0, self.valueCount):
                 self.normals.append(c4d.Vector(self.readFloat(), self.readFloat(), self.readFloat()))

            if (options & 3) == 3:
                for i in range(0, self.valueCount):
                    self.textures.append(c4d.Vector(self.readFloat(), self.readFloat(), 0))

            for i in range(0, self.faceCount):
                self.faces.append({'a': self.readInt(), 'b': self.readInt(), 'c': self.readInt()})

            if (options & 48) == 48:
                num = self.readInt()
                self.offset += (num * 4) + (self.indexCount * 4)
                num = self.readInt()
                self.offset += (3 * num * 4) + (self.indexCount * 4)

            bonelength = self.readInt()
            self.bonemap = [0] * self.valueCount

            if (bonelength > self.valueCount) or (bonelength > self.faceCount):
                datastart = self.offset
                self.offset += bonelength
                for i in range(0, self.valueCount):
                    boneoffset = self.readInt() + 4
                    self.bonemap[i] = self.read_Int(datastart + boneoffset)
    
    def read_Int(self,_offset):
        return struct.unpack_from('i', self.data, _offset)[0]

    def readInt(self):
        ret = struct.unpack_from('i', self.data, self.offset)[0]
        self.offset += 4
        return int(ret)

    def readFloat(self):
        ret = struct.unpack_from('f', self.data, self.offset)[0]
        self.offset += 4
        return float(ret)

class Geometrie(object):
    def __init__(self, designID, database):
        self.designID = designID
        self.Parts = {}
        self.Partname = ''
        GeometrieLocation = '{0}{1}{2}'.format(GEOMETRIEPATH, self.designID,'.g')
        GeometrieCount = 0
        while str(GeometrieLocation) in database.filelist:
            self.Parts[GeometrieCount] = GeometrieReader(data=database.filelist[GeometrieLocation].read())
            GeometrieCount += 1
            GeometrieLocation = '{0}{1}{2}{3}'.format(GEOMETRIEPATH, self.designID,'.g',GeometrieCount)

        primitive = Primitive(data = database.filelist[PRIMITIVEPATH + self.designID + '.xml'].read())
        self.Partname = primitive.designname
        # preflex
        for part in self.Parts:
            # transform
            for i, b in enumerate(primitive.Bones):
                # positions
                for j, p in enumerate(self.Parts[part].positions):
                    if (self.Parts[part].bonemap[j] == i):
                        self.Parts[part].positions[j] = b.matrix.Mul(p)
                # normals
                for k, n in enumerate(self.Parts[part].normals):
                    if (self.Parts[part].bonemap[k] == i):
                        self.Parts[part].normals[k] = b.matrix.MulV(n)

    def valuecount(self):
        count = 0
        for part in self.Parts:
            count += self.Parts[part].valueCount
        return count

    def facecount(self):
        count = 0
        for part in self.Parts:
            count += self.Parts[part].faceCount
        return count

    def texcount(self):
        count = 0
        for part in self.Parts:
            count += len(self.Parts[part].textures)
        return count

class Bone2():
    def __init__(self,boneId=0, angle=0, ax=0, ay=0, az=0, tx=0, ty=0, tz=0):
        self.matrix = c4d.utils.RotAxisToMatrix(c4d.Vector(ax,ay,az), utils.Rad(angle))
        self.matrix.off = -self.matrix.Mul(c4d.Vector(tx, ty, tz))

class Primitive():
    def __init__(self,data):
        self.designname = ''
        self.Bones = []
        xml = minidom.parseString(data)
        for node in xml.firstChild.childNodes: 
            if node.nodeName == 'Flex': 
                for node in node.childNodes:
                    if node.nodeName == 'Bone':
                        self.Bones.append(Bone2(boneId=int(node.getAttribute('boneId')), angle=float(node.getAttribute('angle')), ax=float(node.getAttribute('ax')), ay=float(node.getAttribute('ay')), az=float(node.getAttribute('az')), tx=float(node.getAttribute('tx')), ty=float(node.getAttribute('ty')), tz=float(node.getAttribute('tz'))))
            elif node.nodeName == 'Annotations':
                for childnode in node.childNodes:
                    if childnode.nodeName == 'Annotation' and childnode.hasAttribute('designname'):
                        self.designname = childnode.getAttribute('designname')

class LOCReader(object):
    def __init__(self, data):
        self.offset = 0
        self.values = {}
        self.data = data
        if ord(self.data[0]) == 50 and ord(self.data[1]) == 0:
            self.offset += 2
            while self.offset < len(self.data):
                key = self.NextString().replace('Material', '')
                value = self.NextString()
                self.values[key] = value

    def NextString(self):
        out = ''
        t = ord(self.data[self.offset])
        self.offset += 1
        while not t == 0:
            out = '{0}{1}'.format(out,chr(t))
            t = ord(self.data[self.offset])
            self.offset += 1
        return out

class Materials(object):
    def __init__(self, data):
        self.Materials = {}
        xml = minidom.parseString(data)
        for node in xml.firstChild.childNodes: 
            if node.nodeName == 'Material':
                self.Materials[node.getAttribute('MatID')] = Material(r=int(node.getAttribute('Red')), g=int(node.getAttribute('Green')), b=int(node.getAttribute('Blue')), a=int(node.getAttribute('Alpha')), mtype=str(node.getAttribute('MaterialType')))

    def setLOC(self, loc):
        for key in loc.values:
            if key in self.Materials:
                self.Materials[key].name = loc.values[key]

    def getMaterialbyId(self, mid):
        return self.Materials[mid]

class Material(object):
    def __init__(self, r, g, b, a, mtype):
        self.name = ''
        self.mattype = mtype
        self.r = float(r)
        self.g = float(g)
        self.b = float(b)
        self.a = float(a)

class LIFFile():
    def __init__(self, name, offset, size, handle):
        self.handle = handle
        self.name = name
        self.offset = offset
        self.size = size

    def read(self):
        self.handle.seek(self.offset, 0)
        return self.handle.read(self.size)

class LIFReader(object):
    def __init__(self, file):
        self.packedFilesOffset = 84
        self.filelist = {}
        self.initok = False
        self.location = file
        self.dbinfo = None
        try:
            self.filehandle = open(self.location, "rb")
            self.filehandle.seek(0, 0)
        except Exception as e:
            gui.MessageDialog(e, c4d.GEMB_OK)
            self.initok = False
            return
        else:
            if self.filehandle.read(4) == "LIFF":
                self.parse(prefix='', offset=self.readInt(offset=72) + 64)
                if '/Materials.xml' in self.filelist and '/info.xml' in self.filelist:
                    self.dbinfo = DBinfo(data=self.filelist['/info.xml'].read())
                    print "Database OK."
                    self.initok = True
            else:
                print "Database FAIL"
                self.initok = False

    def parse(self, prefix='', offset=0):
        if prefix == '':
            offset += 36
        else:
            offset += 4

        count = self.readInt(offset=offset)

        for i in range(0, count):
            offset += 4
            entryType = self.readShort(offset=offset)
            offset += 6

            entryName = '{0}{1}'.format(prefix,'/');
            self.filehandle.seek(offset + 1, 0)
            t = ord(self.filehandle.read(1))

            while not t == 0:
                entryName ='{0}{1}'.format(entryName,chr(t))
                self.filehandle.seek(1, 1)
                t = ord(self.filehandle.read(1));
                offset += 2

            offset += 6
            self.packedFilesOffset += 20

            if entryType == 1:
                offset = self.parse(prefix=entryName, offset=offset)
            elif entryType == 2:
                fileSize = self.readInt(offset=offset) - 20
                self.filelist[entryName] = LIFFile(name=entryName, offset=self.packedFilesOffset, size=fileSize, handle=self.filehandle)
                offset += 24
                self.packedFilesOffset += fileSize

        return offset

    def readInt(self, offset=0):
        self.filehandle.seek(offset, 0)
        return int(self.filehandle.read(4).encode('hex'), 16)

    def readShort(self, offset=0):
        self.filehandle.seek(offset, 0)
        return int(self.filehandle.read(2).encode('hex'), 8)

class DBinfo(object):
    def __init__(self, data):
        xml = minidom.parseString(data)
        self.Version = xml.getElementsByTagName('Bricks')[0].attributes['version'].value
        print 'Database Brickversion: ' + str(self.Version)

class LDDDialog(gui.GeDialog):
    LDDData = None
    databaselocation = None
    texturestring = None
    textureexport = False
    allMaterials = None
    Scenefile = None

    def CreateLayout(self):
        self.SetTitle("LDD2C4D - " + VERSION)

        self.MenuFlushAll()
        self.MenuSubBegin("Info")
        self.MenuAddString(IDM_ABOUT, "About")

        self.MenuSubEnd()
        self.MenuFinished()

        self.GroupBegin(100, c4d.BFH_SCALEFIT, 1, 1)
        self.GroupBorderSpace(5, 5, 5, 5)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 20, 1, 'Database', 0)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.AddStaticText(id=IDC_TEXT_DATABASE, flags=c4d.BFH_SCALEFIT, initw=0, inith=0, name='', borderstyle=c4d.BORDER_THIN_IN)
        self.AddButton(id=IDC_BUTTON_DATABASE, flags=c4d.BFH_RIGHT, initw=8, inith=8, name="...")
        self.GroupEnd()

        self.GroupBegin(id=0, flags=c4d.BFH_SCALEFIT, cols=20, rows=1, title='Instance', groupflags=0)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.AddCheckbox(id=IDC_INSTANCES, flags=c4d.BFH_LEFT, initw=0, inith=0, name='Generate Instance Objects')
        self.AddCheckbox(id=IDC_RENDERINSTANCES, flags=c4d.BFH_RIGHT|c4d.BFH_SCALEFIT, initw=0, inith=0, name='Render Instances')
        self.SetBool(IDC_INSTANCES, True)
        self.SetBool(IDC_RENDERINSTANCES, True)
        self.GroupEnd()

        self.GroupBegin(id=0, flags=c4d.BFH_SCALEFIT, cols=20, rows=1, title="Scale", groupflags=0)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.AddEditSlider(id=IDC_SLIDER_SCALE, flags=c4d.BFH_SCALEFIT, initw=0, inith=0)
        self.SetInt32(IDC_SLIDER_SCALE, 20, min=1, max=100, step=1, tristate=False)
        self.GroupEnd()

        self.GroupBegin(id=0, flags=c4d.BFH_SCALEFIT, cols=20, rows=1, title='Decoration', groupflags=0)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.AddCheckbox(id=IDC_EXPORT_TEX, flags=c4d.BFH_LEFT, initw=0, inith=0, name='Export Texture')
        self.AddStaticText(id=IDC_TEXT_TEXTURE, flags=c4d.BFH_SCALEFIT, initw=0, inith=0, name=self.texturestring, borderstyle=c4d.BORDER_THIN_IN)
        self.AddButton(id=IDC_BUTTON_TEXTURE, flags=c4d.BFH_RIGHT, initw=8, inith=8, name="...")
        self.Enable(IDC_TEXT_TEXTURE, self.textureexport)
        self.Enable(IDC_BUTTON_TEXTURE, self.textureexport)
        self.GroupEnd()

        self.GroupBegin(id=0, flags=c4d.BFH_SCALEFIT, cols=20, rows=1, title='Material Template', groupflags=0)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(5, 5, 5, 5)
        self.AddStaticText(id=IDC_TEXT_MAT_TEMPLATE, flags=c4d.BFH_LEFT, initw=0, inith=0, name="Please drag material here:")
        self.linkTemplate = self.AddCustomGui(id=IDC_MAT_LINK, pluginid=c4d.CUSTOMGUI_LINKBOX, name="materialTemplate", flags=c4d.BFH_SCALEFIT, minw=0, minh=0)
        self.GroupEnd()

        self.AddButton(id=IDC_BUTTON_LOAD, flags=c4d.BFH_CENTER, initw=200, inith=25, name='Load Model')
        self.Enable(IDC_BUTTON_LOAD, False)

        self.GroupEnd()
        return True

    def Command(self, id, msg):
        if id == IDM_ABOUT:
            self.About()
        elif id == IDC_BUTTON_DATABASE:
            self.OpenDatabase()
        elif id == IDC_BUTTON_LOAD:
            self.Load()
        elif id == IDC_BUTTON_TEXTURE:
            self.texturestring = c4d.storage.LoadDialog(flags=c4d.FILESELECT_DIRECTORY, title='select texture path')
            self.ChecktexturePath()
        elif id == IDC_EXPORT_TEX:
            self.ChecktexturePath()
        elif id == IDC_INSTANCES:
            self.Enable(IDC_RENDERINSTANCES, self.GetBool(IDC_INSTANCES))
        return True
    
    @staticmethod
    def About():
        gui.MessageDialog("LDD2C4D - " + VERSION + " by jonnysp 2016", c4d.GEMB_OK)
        return True

    def ChecktexturePath(self):
        if self.GetBool(IDC_EXPORT_TEX):
            # Check path exist
            if not (str(self.texturestring) == 'None'):
                if (os.path.isdir(self.texturestring) == False):
                    self.texturestring = 'None'
            else:
                self.texturestring = c4d.storage.LoadDialog(flags=c4d.FILESELECT_DIRECTORY, title='select texture path')

            if (str(self.texturestring) == 'None'):
                self.textureexport = False
            else:
                self.textureexport = True
        else:
            self.textureexport = False

        self.SetBool(IDC_EXPORT_TEX,self.textureexport)
        self.Enable(IDC_TEXT_TEXTURE, self.textureexport)
        self.Enable(IDC_BUTTON_TEXTURE, self.textureexport)
        self.SetString(IDC_TEXT_TEXTURE,self.texturestring)
        self.UpdatePrefs()
        return self.textureexport

    def OpenDatabase(self):
        self.databaselocation = c4d.storage.LoadDialog(type=c4d.FILESELECTTYPE_ANYTHING, title="Select Database (lif)", force_suffix="lif")
        self.SetString(IDC_TEXT_DATABASE, self.databaselocation)
        self.UpdatePrefs()
        self.Enable(IDC_BUTTON_LOAD, False)
        if not (str(self.databaselocation) == 'None'):
            self.TestDatabase()
        return True

    def InitValues(self):
        self.LDDData = plugins.GetWorldPluginData(id = PLUGIN_ID)
        if self.LDDData:
            self.databaselocation = self.LDDData[DATABASE]
            self.texturestring = self.LDDData[TEXTUR]
            self.SetString(IDC_TEXT_DATABASE, self.databaselocation)
            self.SetString(IDC_TEXT_TEXTURE, self.texturestring)
            if not (str(self.databaselocation) == 'None'):
                self.TestDatabase()
            else:
                if os.name =='posix':
                    testfile = str(os.path.join(str(os.getenv('USERPROFILE') or os.getenv('HOME')),'Library','Application Support','LEGO Company','LEGO Digital Designer','db.lif'))
                else:
                    testfile = str(os.path.join(str(os.getenv('USERPROFILE') or os.getenv('HOME')),'AppData','Roaming','LEGO Company','LEGO Digital Designer','db.lif'))
                
                if os.path.isfile(testfile):
                    self.databaselocation = testfile
                    self.SetString(IDC_TEXT_DATABASE, self.databaselocation)
                    self.TestDatabase()
            if not (str(self.texturestring) == 'None'):
                self.ChecktexturePath()
        else:
            self.LDDData = c4d.BaseContainer()
        return True

    def UpdatePrefs(self):
        self.LDDData.SetString(DATABASE, self.databaselocation)
        self.LDDData.SetString(TEXTUR, self.texturestring)
        plugins.SetWorldPluginData(PLUGIN_ID,self.LDDData)
        return True

    def TestDatabase(self):
        self.database = LIFReader(file=self.databaselocation)

        if self.database.initok:
            self.Enable(IDC_BUTTON_LOAD, True)
            self.allMaterials = Materials(data=self.database.filelist['/Materials.xml'].read());
            self.allMaterials.setLOC(loc=LOCReader(data=self.database.filelist[MATERIALNAMESPATH + 'EN/localizedStrings.loc'].read()))
        else:
            self.Enable(IDC_BUTTON_LOAD, False)
        return True

    def Load(self):
        self.Scenefile = c4d.storage.LoadDialog(type=c4d.FILESELECTTYPE_ANYTHING, title="select LDD File (lxf or lxfml)", force_suffix="lxf|lxfml")
        if not (self.Scenefile is None):
            if self.Scenefile[-4:].lower() not in (".lxf", "xfml"):
                gui.MessageDialog('Invalid File Type Must be a .lxf or .lxfml', c4d.GEMB_OK)
                return
        else:
            return

        self.Scene = Scene(file=self.Scenefile)

        if not self.database.dbinfo.Version == self.Scene.Version:
            if gui.QuestionDialog("The scene version differs from the database version, which can lead to errors. Continue?") == False:
                return

        start_time = time.time()
        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()

        scenenode = c4d.BaseObject(c4d.Onull)
        scenenode.SetName(self.Scene.Name)

        instancnode = c4d.BaseObject(c4d.Onull)
        instancnode.SetName('InstanceParts')
        instancnode[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = True
        instancnode[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = True

        geometriecache = {}
        instancescache = {}

        statuscount = 0
        allcount = len(self.Scene.Bricks)

        for bri in self.Scene.Bricks:

            statuscount += 1
            c4d.StatusSetBar(statuscount * 100 / allcount)

            for pa in bri.Parts:

                #cache geometrie is not flex
                if len(pa.Bones) > 1 or self.GetBool(IDC_INSTANCES) == False:
                    geo = Geometrie(designID=pa.designID, database=self.database)
                else:
                    if pa.designID not in geometriecache:
                        geo = Geometrie(designID=pa.designID, database=self.database)
                        geometriecache[pa.designID] = geo
                    else:
                        geo = geometriecache[pa.designID]

                c4d.StatusSetText(geo.Partname)
                
                obj = c4d.PolygonObject(geo.valuecount(), geo.facecount())
                obj.SetName(geo.Partname)
    
                #if not in instancescache fill PolygonObject
                if pa.designID not in instancescache:

                    # transform -------------------------------------------------------
                    for part in geo.Parts:
                        if len(pa.Bones) > 1 or self.GetBool(IDC_INSTANCES) == False:
                            for i, b in enumerate(pa.Bones):
                                # positions
                                for j, p in enumerate(geo.Parts[part].positions):
                                    if (geo.Parts[part].bonemap[j] == i):
                                        geo.Parts[part].positions[j] = b.matrix.Mul(p) * self.GetInt32(IDC_SLIDER_SCALE)
                                # normals
                                for k, n in enumerate(geo.Parts[part].normals):
                                    if (geo.Parts[part].bonemap[k] == i):
                                        geo.Parts[part].normals[k] = b.matrix.MulV(n)
                        else:
                            for j, p in enumerate(geo.Parts[part].positions):
                                geo.Parts[part].positions[j] = FLIP.MulV(p) * self.GetInt32(IDC_SLIDER_SCALE)
                            
                            for i, b in enumerate(pa.Bones):
                                for k, n in enumerate(geo.Parts[part].normals):
                                    if (geo.Parts[part].bonemap[k] == i):
                                        geo.Parts[part].normals[k] = FLIP.MulV(n)
                    # -----------------------------------------------------------------

                    #calc center--------------------------------------------------------
                    if len(pa.Bones) > 1 or self.GetBool(IDC_INSTANCES) == False:

                        min_x = max_x = geo.Parts[0].positions[0].x
                        min_y = max_y = geo.Parts[0].positions[0].y
                        min_z = max_z = geo.Parts[0].positions[0].z
                        for part in geo.Parts:
                            for j, p in enumerate(geo.Parts[part].positions):
                                if p.x > max_x: max_x = p.x
                                if p.x < min_x: min_x = p.x
                                if p.y > max_y: max_y = p.y
                                if p.y < min_y: min_y = p.y
                                if p.z > max_z: max_z = p.z
                                if p.z < min_z: min_z = p.z

                        center = c4d.Vector(max_x + min_x , max_y + min_y , max_z + min_z) * 0.5

                        #apply center
                        for part in geo.Parts:
                            for j, p in enumerate(geo.Parts[part].positions):
                                geo.Parts[part].positions[j] -= center

                        obj.SetAbsPos(center)
                    # -----------------------------------------------------------------

                    #Add Points ----------------------------------------------------------
                    points = []
                    for part in geo.Parts:
                        points.extend(geo.Parts[part].positions)
                    obj.SetAllPoints(points)
                    # -----------------------------------------------------------------

                    #Add Point Selection in Flexparts ---------------------------------
                    for part in geo.Parts:
                        if len(pa.Bones) > 1:
                            for i, b in enumerate(pa.Bones):
                                bmap = [x for x, j in enumerate(geo.Parts[part].bonemap) if j == i]
                                if len(bmap) > 0:
                                    selp = c4d.SelectionTag(c4d.Tpointselection)
                                    selp[c4d.ID_BASELIST_NAME] = str(i)
                                    bs = selp.GetBaseSelect()
                                    for p in bmap:
                                        bs.Select(p)
                                    obj.InsertTag(selp)
                    #------------------------------------------------------------------  

                    #Add faces  ----------------------------------------------
                    indexOffset = 0
                    faceOffset = 0
                    for part in geo.Parts:
    
                        selp = c4d.SelectionTag(c4d.Tpolygonselection)
                        selp[c4d.ID_BASELIST_NAME] = str(part)
                        bs = selp.GetBaseSelect()
    
                        for i, face in enumerate(geo.Parts[part].faces): 
                            obj.SetPolygon(i + faceOffset, c4d.CPolygon(face['c'] + indexOffset, face['b'] + indexOffset, face['a'] + indexOffset))
                            bs.Select(i + faceOffset)
    
                        indexOffset += geo.Parts[part].valueCount
                        faceOffset += geo.Parts[part].faceCount
                        obj.InsertTag(selp)
                    # -----------------------------------------------------------------
    
                    #Add textures --------------------------------------------------------
                    if geo.texcount() > 0:
                        faceOffset = 0
                        uvwtag = obj.MakeVariableTag(c4d.Tuvw, geo.facecount())
                        for part in geo.Parts:
                            if len(geo.Parts[part].textures) > 0:
                                for i, face in enumerate(geo.Parts[part].faces): 
                                    uvwtag.SetSlow(i + faceOffset, geo.Parts[part].textures[face['c']], geo.Parts[part].textures[face['b']], geo.Parts[part].textures[face['a']], c4d.Vector(0, 0, 0))
                            faceOffset += geo.Parts[part].faceCount
                        obj.InsertTag(uvwtag)
                    # -----------------------------------------------------------------

                    #Add normals ---------------------------------------------------------
                    normalOffset = 0
                    normaltag = obj.MakeVariableTag(c4d.Tnormal, obj.GetPolygonCount())
                    for part in geo.Parts:
                        for i, face in enumerate(geo.Parts[part].faces): 
                            self.set_normals(normaltag, i + normalOffset, geo.Parts[part].normals[face['c']], geo.Parts[part].normals[face['b']], geo.Parts[part].normals[face['a']], c4d.Vector(0, 0, 0))
                        normalOffset += geo.Parts[part].faceCount
                    obj.InsertTag(normaltag)
                    # -----------------------------------------------------------------

                    obj.SetPhong(True, True, c4d.utils.Rad(23))
                    obj.Message(c4d.MSG_UPDATE)


                #if flex add part without Instance
                if len(pa.Bones) > 1 or self.GetBool(IDC_INSTANCES) == False:

                    #Add material ----------------------------------------------
                    decoCount = 0
                    for part in geo.Parts:
                        # decoration
                        if self.GetBool(IDC_EXPORT_TEX):
                            deco = '0'
                            if hasattr(pa, 'decoration') and len(geo.Parts[part].textures) > 0:
                                if decoCount <= len(pa.decoration):
                                    deco = pa.decoration[decoCount]
                                decoCount += 1
    
                            dec = self.buildDecoration(doc=doc, deco=deco)
                            if not dec is None:
                                decotag = c4d.TextureTag()
                                decotag.SetMaterial(dec)
                                decotag[c4d.TEXTURETAG_RESTRICTION] = str(part)
                                decotag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
                                decotag[c4d.TEXTURETAG_TILE] = False
                                obj.InsertTag(decotag)
    
                        # color
                        lddmat = self.allMaterials.getMaterialbyId(pa.materials[part])
                        mat = self.buildMaterial(doc=doc, lddmat=lddmat)
                        textag = c4d.TextureTag()
                        textag.SetMaterial(mat)
                        textag[c4d.TEXTURETAG_RESTRICTION] = str(part)
                        textag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
                        obj.InsertTag(textag)
                    # -----------------------------------------------------------------

                    obj.InsertUnder(scenenode) 

                #add Instance part
                else:

                    pa.Bones[0].matrix.off *= self.GetInt32(IDC_SLIDER_SCALE)

                    ins = c4d.BaseObject(c4d.Oinstance)
                    ins[c4d.INSTANCEOBJECT_RENDERINSTANCE] = self.GetBool(IDC_RENDERINSTANCES)

                    if pa.designID in instancescache:
                        ins[c4d.INSTANCEOBJECT_LINK] = instancescache[pa.designID]
                        ins.SetName(instancescache[pa.designID].GetName())
                    else:
                        instancescache[pa.designID] = obj
                        obj.InsertUnder(instancnode)
                        ins[c4d.INSTANCEOBJECT_LINK] = obj
                        ins.SetName(obj.GetName())

                    #Add material to instance ----------------------------------------------
                    decoCount = 0
                    for part in geo.Parts:
                        # decoration
                        if self.GetBool(IDC_EXPORT_TEX):
                            deco = '0'
                            if hasattr(pa, 'decoration') and len(geo.Parts[part].textures) > 0:
                                if decoCount <= len(pa.decoration):
                                    deco = pa.decoration[decoCount]
                                decoCount += 1
    
                            dec = self.buildDecoration(doc=doc, deco=deco)
                            if not dec is None:
                                decotag = c4d.TextureTag()
                                decotag.SetMaterial(dec)
                                decotag[c4d.TEXTURETAG_RESTRICTION] = str(part)
                                decotag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
                                decotag[c4d.TEXTURETAG_TILE] = False
                                ins.InsertTag(decotag)

                        # color
                        lddmat = self.allMaterials.getMaterialbyId(pa.materials[part])
                        mat = self.buildMaterial(doc=doc, lddmat=lddmat)
                        textag = c4d.TextureTag()
                        textag.SetMaterial(mat)
                        textag[c4d.TEXTURETAG_RESTRICTION] = str(part)
                        textag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
                        ins.InsertTag(textag)
                    #----------------------------------------------------------------------  

                    ins.SetMg(pa.Bones[0].matrix * FLIP)
                    ins.InsertUnder(scenenode)

        if self.GetBool(IDC_INSTANCES):
            instancnode.InsertUnder(scenenode)  

        scenenode.Message(c4d.MSG_UPDATE)
        doc.InsertObject(scenenode)
        doc.Message(c4d.MSG_UPDATE)
        doc.AddUndo(c4d.UNDOTYPE_NEW, scenenode)
        c4d.EventAdd(c4d.EVENT_FORCEREDRAW)
        c4d.StatusClear()
        print("--- %s seconds ---" % (time.time() - start_time))

    def buildDecoration(self, doc, deco='0'):
        extfile = ''
        if not deco == '0':
            extfile = os.path.join(self.texturestring, deco + '.png')
            if not os.path.isfile(extfile):
                with open(extfile, "wb") as f:
                    f.write(self.database.filelist[DECORATIONPATH + deco + '.png'].read())
                    f.close()

            m = doc.SearchMaterial(str(deco))
            if (m is None):
                
                if self.linkTemplate.GetLink() == None:
                    m = c4d.BaseMaterial(c4d.Mmaterial)
                else:
                    m = self.linkTemplate.GetLink().GetClone()

                m[c4d.ID_BASELIST_NAME] = str(deco)

                if ( m.CheckType(MATERIAL_TYPE_C4D)):
                    
                    shdr_texture = c4d.BaseList2D(c4d.Xbitmap)
                    shdr_texture[c4d.BITMAPSHADER_FILENAME] = str(extfile)
                    m[c4d.MATERIAL_COLOR_SHADER] = shdr_texture
                    m.InsertShader(shdr_texture)
    
                    shdr_alpha = c4d.BaseList2D(c4d.Xbitmap)
                    shdr_alpha[c4d.BITMAPSHADER_FILENAME] = str(extfile)
                    m[c4d.MATERIAL_USE_ALPHA] = True
                    m[c4d.MATERIAL_ALPHA_SHADER] = shdr_alpha
                    m.InsertShader(shdr_alpha)

                m.Update(True, False)
                doc.InsertMaterial(m)

            return m

    def buildMaterial(self, doc, lddmat):
        m = doc.SearchMaterial(str(lddmat.name))
        if (m is None):
            if self.linkTemplate.GetLink() == None:
                m = c4d.BaseMaterial(c4d.Mmaterial)
            else:
                m = self.linkTemplate.GetLink().GetClone()
             
            m[c4d.ID_BASELIST_NAME] = str(lddmat.name)

            if (m.CheckType(MATERIAL_TYPE_C4D)):
                m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(lddmat.r / 255, lddmat.g / 255, lddmat.b / 255) 

                if lddmat.a < 255:
                    m[c4d.MATERIAL_USE_COLOR] = False
                    m[c4d.MATERIAL_USE_TRANSPARENCY] = True
                    m[c4d.MATERIAL_TRANSPARENCY_BRIGHTNESS] = 1  # lddmat.a / 255
                    m[c4d.MATERIAL_TRANSPARENCY_REFRACTION] = 1.575
                    m[c4d.MATERIAL_TRANSPARENCY_COLOR] = c4d.Vector(lddmat.r / 255, lddmat.g / 255, lddmat.b / 255)
                else:
                    m[c4d.MATERIAL_USE_COLOR] = True
            
            doc.InsertMaterial(m)
            m.Update(True, False)
        return m
    
    @staticmethod
    def float2bytes(f):
        f = int(round(f * 32000))
        if f > 32767:
            f = 32767
        elif f < -32767:
            f = -32767
        p = struct.pack('h', f)
        return (p[0], p[1])

    def set_normals(self, normal_tag, polygon, normal_a, normal_b, normal_c, normal_d):
        normal_list = [normal_a, normal_b, normal_c, normal_d]
        normal_buffer = normal_tag.GetLowlevelDataAddressW()
        for v in range(0, 4):
            normal = normal_list[v]
            component = [normal.x, normal.y, normal.z]
            for c in range(0, 3):
                low_byte, high_byte = self.float2bytes(component[c])
                normal_buffer[24 * polygon + v * 6 + c * 2 + 0] = low_byte
                normal_buffer[24 * polygon + v * 6 + c * 2 + 1] = high_byte
        normal_tag.Message(c4d.MSG_UPDATE)

class MainPlugin(plugins.CommandData):
    dialog = None

    def Execute(self, doc):
        if self.dialog is None:
            self.dialog = LDDDialog()
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=400, defaulth=500)

    def RestoreLayout(self, sec_ref):
        if self.dialog is None:
            self.dialog = LDDDialog()
        return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)

if __name__ == "__main__":
    bmp = bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    fn = os.path.join(dir, "res", "icon.png")
    bmp.InitWith(fn)
    plugins.RegisterCommandPlugin(id=PLUGIN_ID, str="LDD2C4D", info=0, help="Import LDD Files to Cinema4D", dat=MainPlugin(), icon=bmp)
