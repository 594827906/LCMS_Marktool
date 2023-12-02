from functools import partial
from PyQt5 import QtWidgets, QtGui, QtCore
from utils.show_list import ClickableListWidget, FileListWidget, PeakListWidget, ProgressBarsListItem, ProgressBarsList
from utils.roi import construct_tic, construct_eic
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from utils.threading import Worker


class PlotWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self._thread_pool = QtCore.QThreadPool()
        self._pb_list = ProgressBarsList(self)
        self._plotted_list = []

        self._feature_parameters = None

        self._figure = plt.figure()
        self._ax = self._figure.add_subplot(111)  # plot here
        self._ax.set_xlabel('Retention time [min]')
        self._ax.set_ylabel('Intensity')
        self._ax.ticklabel_format(axis='y', scilimits=(0, 0))
        self._label2line = dict()  # a label (aka line name) to plotted line
        self._canvas = FigureCanvas(self._figure)
        self._toolbar = NavigationToolbar(self._canvas, self)

    def run_thread(self, caption: str, worker: Worker, text=None, icon=None):
        pb = ProgressBarsListItem(caption, parent=self._pb_list)
        self._pb_list.addItem(pb)
        worker.signals.progress.connect(pb.setValue)
        worker.signals.operation.connect(pb.setLabel)
        worker.signals.finished.connect(partial(self._threads_finisher,
                                                text=text, icon=icon, pb=pb))
        self._thread_pool.start(worker)

    def _threads_finisher(self, text=None, icon=None, pb=None):
        if pb is not None:
            self._pb_list.removeItem(pb)
            pb.setParent(None)
        if text is not None:
            msg = QtWidgets.QMessageBox(self)
            msg.setText(text)
            msg.setIcon(icon)
            msg.exec_()

    def set_features(self, obj):
        features, parameters = obj
        self._list_of_features.clear()
        for feature in sorted(features, key=lambda x: x.mz):
            self._list_of_features.add_feature(feature)
        self._feature_parameters = parameters

    def scroll_event(self, event):  # 滚轮缩放
        x_min, x_max = event.inaxes.get_xlim()
        x_range = (x_max - x_min) / 10
        if event.button == 'up':
            event.inaxes.set(xlim=(x_min + x_range, x_max - x_range))
            print('up')
        elif event.button == 'down':
            event.inaxes.set(xlim=(x_min - x_range, x_max + x_range))
            print('down')
        self._canvas.draw_idle()

    def button_press(self, event):  # 右键清空画布
        if event.button == 1:
            print('1')
        if event.button == 2:
            print('2')
        if event.button == 3:
            print('3')
            print(self._plotted_list, 'event in')
            self._ax.cla()
            self._label2line.clear()
            self._plotted_list.clear()
            print(self._plotted_list, 'event end')
            self._canvas.draw_idle()

    def plotter(self, obj):
        if not self._label2line:  # in case if 'feature' was plotted
            self._figure.clear()
            self._ax = self._figure.add_subplot(111)
            self._ax.set_title('TIC diagram')
            self._ax.set_xlabel('Retention time [min]')
            self._ax.set_ylabel('Intensity')
            self._ax.ticklabel_format(axis='y', scilimits=(0, 0))  # 使用科学计数法

        line = self._ax.plot(obj['x'], obj['y'], label=obj['label'])
        self._label2line[obj['label']] = line[0]  # save line
        self._ax.legend(loc='best')
        self._figure.tight_layout()
        self._figure.canvas.mpl_connect('scroll_event', self.scroll_event)  # 鼠标滚轮缩放画布
        self._figure.canvas.mpl_connect('button_press_event', self.button_press)  # 右键清空画布
        self._canvas.draw()


    def close_file(self, item):
        self._list_of_files.deleteFile(item)

    def get_selected_files(self):
        return self._list_of_files.selectedItems()

    def get_selected_features(self):
        return self._list_of_features.selectedItems()

    def get_plotted_lines(self):
        return list(self._label2line.keys())

    def plot_feature(self, item, shifted=True):
        feature = self._list_of_features.get_feature(item)
        self._label2line = dict()  # empty plotted TIC and EIC
        self._figure.clear()
        self._ax = self._figure.add_subplot(111)
        feature.plot(self._ax, shifted=shifted)
        self._ax.set_title(item.text())
        self._ax.set_xlabel('Retention time')
        self._ax.set_ylabel('Intensity')
        self._ax.ticklabel_format(axis='y', scilimits=(0, 0))
        self._figure.tight_layout()
        self._canvas.draw()  # refresh canvas

    def plot_tic(self, file):
        label = f'TIC: {file[:file.rfind(".")]}'
        plotted = False
        print(label, plotted, self._plotted_list, 'plot in')
        if label not in self._label2line:
            path = self._list_of_files.file2path[file]

            pb = ProgressBarsListItem(f'Plotting TIC: {file}', parent=self._pb_list)
            self._pb_list.addItem(pb)
            worker = Worker(construct_tic, path, label)
            worker.signals.progress.connect(pb.setValue)
            worker.signals.result.connect(self.plotter)
            worker.signals.finished.connect(partial(self._threads_finisher, pb=pb))

            self._thread_pool.start(worker)

            self._plotted_list.append(label)
            print(self._plotted_list)
            print('plotted')

            plotted = True
        return plotted, label

    def plot_eic(self, file, mz, delta):
        label = f'EIC {mz:.4f} ± {delta:.4f}: {file[:file.rfind(".")]}'
        plotted = False
        if label not in self._label2line:
            path = self._list_of_files.file2path[file]

            pb = ProgressBarsListItem(f'Plotting EIC (mz={mz:.4f}): {file}', parent=self._pb_list)
            self._pb_list.addItem(pb)
            worker = Worker(construct_eic, path, label, mz, delta)
            worker.signals.progress.connect(pb.setValue)
            worker.signals.result.connect(self.plotter)
            worker.signals.finished.connect(partial(self._threads_finisher, pb=pb))

            self._thread_pool.start(worker)

            plotted = True
        return plotted, label

    def delete_line(self, label):
        self._ax.lines.remove(self._label2line[label])
        del self._label2line[label]

    def refresh_canvas(self):
        if self._label2line:
            self._ax.legend(loc='best')
            self._ax.relim()  # recompute the ax.dataLim
            self._ax.autoscale_view()  # update ax.viewLim using the new dataLim
        else:
            self._figure.clear()
            self._ax = self._figure.add_subplot(111)
            self._ax.set_xlabel('Retention time [min]')
            self._ax.set_ylabel('Intensity')
            self._ax.ticklabel_format(axis='y', scilimits=(0, 0))
        self._canvas.draw()


class EICParameterWindow(QtWidgets.QDialog):
    def __init__(self, parent: PlotWindow):
        self.parent = parent
        super().__init__(self.parent)
        self.setWindowTitle('EIC plot option')

        mz_layout = QtWidgets.QHBoxLayout()
        mz_label = QtWidgets.QLabel(self)
        mz_label.setText('m/z=')
        self.mz_getter = QtWidgets.QLineEdit(self)
        self.mz_getter.setText('100.000')
        mz_layout.addWidget(mz_label)
        mz_layout.addWidget(self.mz_getter)

        delta_layout = QtWidgets.QHBoxLayout()
        delta_label = QtWidgets.QLabel(self)
        delta_label.setText('delta=±')
        self.delta_getter = QtWidgets.QLineEdit(self)
        self.delta_getter.setText('0.005')
        delta_layout.addWidget(delta_label)
        delta_layout.addWidget(self.delta_getter)

        plot_button = QtWidgets.QPushButton('Plot')
        plot_button.clicked.connect(self.plot)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(mz_layout)
        layout.addLayout(delta_layout)
        layout.addWidget(plot_button)
        self.setLayout(layout)

    def plot(self):
        try:
            mz = float(self.mz_getter.text())
            delta = float(self.delta_getter.text())
            for file in self.parent.get_selected_files():
                file = file.text()
                self.parent.plot_eic(file, mz, delta)
            self.close()
        except ValueError:
            # popup window with exception
            msg = QtWidgets.QMessageBox(self)
            msg.setText("'m/z' and 'delta' should be float numbers!")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
