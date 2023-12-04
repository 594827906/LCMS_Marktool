import os
import json
from PyQt5 import QtWidgets, QtCore, QtGui


def find_mzML(path, array=None):
    if array is None:
        array = []
    for obj in os.listdir(path):
        obj_path = os.path.join(path, obj)
        if os.path.isdir(obj_path):  # object is a directory
            find_mzML(obj_path, array)
        elif obj_path[-4:] == 'mzML':  # object is mzML file
            array.append(obj_path)
    return array


class ClickableListWidget(QtWidgets.QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.double_click = None
        self.right_click = None

    def mousePressEvent(self, QMouseEvent):
        super(QtWidgets.QListWidget, self).mousePressEvent(QMouseEvent)
        if QMouseEvent.button() == QtCore.Qt.RightButton and self.right_click is not None:
            self.right_click()

    def mouseDoubleClickEvent(self, QMouseEvent):
        if self.double_click is not None:
            if QMouseEvent.button() == QtCore.Qt.LeftButton:
                item = self.itemAt(QMouseEvent.pos())
                if item is not None:
                    self.double_click(item)

    def connectDoubleClick(self, method):
        """
        Set a callable object which should be called when a user double-clicks on item
        Parameters
        ----------
        method : callable
            any callable object
        Returns
        -------
        - : None
        """
        self.double_click = method

    def connectRightClick(self, method):
        """
        Set a callable object which should be called when a user double-clicks on item
        Parameters
        ----------
        method : callable
            any callable object
        Returns
        -------
        - : None
        """
        self.right_click = method


class FileListWidget(ClickableListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file2path = {}

    def addFile(self, path: str):
        filename = os.path.basename(path)
        self.file2path[filename] = path
        self.addItem(filename)

    def deleteFile(self, item: QtWidgets.QListWidgetItem):
        del self.file2path[item.text()]
        self.takeItem(self.row(item))

    def getPath(self, item: QtWidgets.QListWidgetItem):
        return self.file2path[item.text()]


class ROIListWidget(ClickableListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file2path = {}

    def addFile(self, path: str):
        filename = os.path.basename(path)
        self.file2path[filename] = path
        with open(path) as json_file:
            roi = json.load(json_file)
        status = roi['label']
        # file_name_label = QtWidgets.QLabel(filename)
        # file_status_label = QtWidgets.QLabel(status)
        item = QtWidgets.QListWidgetItem()
        item.setText(filename)
        if status == 0:
            pass
        elif status == 1:
            pass
        else:  # 高亮未标注的文件
            item.setData(QtCore.Qt.BackgroundRole, QtGui.QColor("yellow"))
        self.addItem(item)

    def refresh_background(self, path: str):
        filename = os.path.basename(path)
        items = self.findItems(filename, QtCore.Qt.MatchExactly)
        item = items[0]
        item.setData(QtCore.Qt.BackgroundRole, QtGui.QColor("white"))

    def deleteFile(self, item: QtWidgets.QListWidgetItem):
        del self.file2path[item.text()]
        self.takeItem(self.row(item))

    def getPath(self, item: QtWidgets.QListWidgetItem):
        return self.file2path[item.text()]


class PeakListWidget(ClickableListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.features = []

    def add_feature(self, feature):
        name = f'#{len(self.features)}: mz = {feature.mz:.4f}, rt = {feature.rtmin:.2f} - {feature.rtmax:.2f}'
        self.features.append(feature)
        self.addItem(name)

    def get_feature(self, item):
        number = item.text()
        number = int(number[number.find('#') + 1:number.find(':')])
        return self.features[number]

    def get_all(self):
        features = []
        for i in range(self.count()):
            item = self.item(i)
            features.append(self.get_feature(item))
        return features

    def clear(self):
        super(PeakListWidget, self).clear()
        self.features = []

class ProgressBarsListItem(QtWidgets.QWidget):
    def __init__(self, text, pb=None, parent=None):
        super().__init__(parent)
        self.pb = pb
        if self.pb is None:
            self.pb = QtWidgets.QProgressBar()

        self.label = QtWidgets.QLabel(self)
        self.label.setText(text)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addWidget(self.label, 30)
        main_layout.addWidget(self.pb, 70)

        self.setLayout(main_layout)

    def setValue(self, value):
        self.pb.setValue(value)

    def setLabel(self, text):
        self.pb.setValue(0)
        self.label.setText(text)

class ProgressBarsList(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

    def removeItem(self, item):
        self.layout().removeWidget(item)

    def addItem(self, item):
        self.layout().addWidget(item)


class GetFolderWidget(QtWidgets.QWidget):
    def __init__(self, default_directory='', parent=None):
        super().__init__(parent)

        button = QtWidgets.QToolButton()
        button.setText('...')
        button.clicked.connect(self.set_folder)

        if not default_directory:
            default_directory = os.getcwd()
        self.lineEdit = QtWidgets.QToolButton()
        self.lineEdit.setText(default_directory)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.lineEdit, 85)
        layout.addWidget(button, 15)

        self.setLayout(layout)

    def set_folder(self):
        directory = str(QtWidgets.QFileDialog.getExistingDirectory())
        if directory:
            self.lineEdit.setText(directory)

    def get_folder(self):
        return self.lineEdit.text()