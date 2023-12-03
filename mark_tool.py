import sys
from utils.plot import PlotWindow, EICParameterWindow
from utils.show_list import find_mzML, FileListWidget, PeakListWidget, ROIListWidget, ProgressBarsListItem
from utils.annotation_window import AnnotationParameterWindow, ReAnnotationParameterWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from functools import partial

class MainWindow(PlotWindow):
    def __init__(self):
        super().__init__()
        # self.init_data()
        self.resize(1344, 756)
        self.init_ui()
        # self._plotted_list = []

        self._list_of_files.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._list_of_files.connectDoubleClick(self.FileListPlot)  # 双击绘制TIC图
        self._list_of_files.connectRightClick(partial(FileListMenu, self))  # 右键打开菜单

        # self._list_of_peaks.connectRightClick(partial(PeakListMenu, self))

    # def init_data(self):
    #     self.field_list: list = []
    #     self.x_field: str = ''
    #     self.current_filename: str = ''
    #     self.cur_len: int = 20

    def init_ui(self):
        self.setWindowTitle('mzml峰标注工具')

        # 左侧布局
        open_file_btn = QtWidgets.QPushButton('导入.mzML文件')
        open_file_btn.clicked.connect(self.open_file_btn)
        gen_roi_btn = QtWidgets.QPushButton('生成ROI并标注')
        gen_roi_btn.clicked.connect(self.gen_roi_btn)
        continue_btn = QtWidgets.QPushButton('继续标注')
        continue_btn.clicked.connect(self.continue_btn)

        file_list_label = QtWidgets.QLabel('文件列表：')

        self._list_of_files = FileListWidget()

        # roi_list_label = QtWidgets.QLabel('ROI列表：')
        # self._list_of_ROIs = ROIListWidget()

        layout_left = QtWidgets.QVBoxLayout()
        layout_left.addWidget(open_file_btn)
        layout_left.addWidget(gen_roi_btn)
        layout_left.addWidget(continue_btn)
        layout_left.addWidget(file_list_label)
        layout_left.addWidget(self._list_of_files, 5)
        # layout_left.addWidget(roi_list_label)
        # layout_left.addWidget(self._list_of_ROIs, 10)

        # 中间布局
        layout_mid = QtWidgets.QHBoxLayout()
        layout_plot = QtWidgets.QVBoxLayout()
        layout_plot.addWidget(self._toolbar)
        layout_plot.addWidget(self._canvas, 9)

        # 进度条布局
        scrollable_pb_list = QtWidgets.QScrollArea()
        scrollable_pb_list.setWidget(self._pb_list)
        scrollable_pb_list.setWidgetResizable(True)
        layout_plot.addWidget(scrollable_pb_list, 1)

        layout_mid.addLayout(layout_plot)

        # 右侧布局
        # peak_list_label = QtWidgets.QLabel('已标记的峰列表：')
        # self._list_of_peaks = PeakListWidget()
        # export_btn = QtWidgets.QPushButton('导出峰列表')
        # export_btn.clicked.connect(self.export_btn)

        # layout_right = QtWidgets.QVBoxLayout()
        # layout_right.addWidget(peak_list_label)
        # layout_right.addWidget(self._list_of_peaks)
        # layout_right.addWidget(export_btn)

        # 主视窗布局
        layout = QtWidgets.QHBoxLayout()
        layout.addLayout(layout_left, 1)
        layout.addLayout(layout_mid, 9)
        # layout.addLayout(layout_right, 1)

        self.setLayout(layout)

    def open_file_btn(self):
        files_names = QtWidgets.QFileDialog.getOpenFileNames(None, '', '', 'mzML (*.mzML)')[0]
        for name in files_names:
            self._list_of_files.addFile(name)

    def gen_roi_btn(self):
        mode = 'manual'
        files = [self._list_of_files.file2path[self._list_of_files.item(i).text()]
                 for i in range(self._list_of_files.count())]
        subwindow = AnnotationParameterWindow(files, mode, self)
        subwindow.show()

    def continue_btn(self):
        mode = 'reannotation'
        subwindow = ReAnnotationParameterWindow(self)
        subwindow.show()

    # def export_btn(self):
    #     if self._list_of_peaks.count() > 0:
    #         # TODO: features should be QTreeWidget (root should keep basic information: files and parameters)
    #         files = self._feature_parameters['files']
    #         table = ResultTable(files, self._list_of_peaks.features)
    #         table.fill_zeros(self._feature_parameters['delta mz'])
    #         file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export features', '',
    #                                                              'csv (*.csv)')
    #         if file_name:
    #             table.to_csv(file_name)
    #     else:
    #         msg = QtWidgets.QMessageBox(self)
    #         msg.setText('列表中没有任何数据\n')
    #         msg.setIcon(QtWidgets.QMessageBox.Warning)
    #         msg.exec_()
    #     pass

    def clear_btn(self):
        self._list_of_files.clear()

    def FileListPlot(self, item):
        for file in self.get_selected_files():
            file = file.text()
            plotted, label = self.plot_tic(file)
            # self.plot_tic(file)
            if plotted:
                self._plotted_list.append(label)


class FileListMenu(QtWidgets.QMenu):
    def __init__(self, parent: MainWindow):
        self.parent = parent
        super().__init__(parent)

        menu = QtWidgets.QMenu(parent)

        # tic = QtWidgets.QAction('绘制TIC', parent)
        # eic = QtWidgets.QAction('Plot EIC', parent)
        # generate = QtWidgets.QAction('标注ROI', parent)
        # mode = 'manual'
        clear = QtWidgets.QAction('清除该TIC图', parent)
        close = QtWidgets.QAction('关闭', parent)

        # menu.addAction(tic)
        # menu.addAction(eic)
        # menu.addAction(generate)
        menu.addAction(clear)
        menu.addAction(close)

        action = menu.exec_(QtGui.QCursor.pos())
        for label in self.parent.get_plotted_lines():
            self.parent._plotted_list.append(label)
        # if action == tic:
        #     for file in self.parent.get_selected_files():
        #         file = file.text()
        #         self.parent.plot_tic(file)
        # elif action == eic:
        #     subwindow = EICParameterWindow(self.parent)
        #     subwindow.show()
        if action == close:
            self.close_files()
        # elif action == clear:
        #     self.delete_tic()

    def delete_tic(self):
        for item in self.parent.get_selected_files():
            self.parent.delete_line(item.text())
            plotted_line = self.parent._plotted_list.row(item)
            self.parent._plotted_list.remove(plotted_line)  # delete item from list
        self.parent.refresh_canvas()

    def close_files(self):
        for item in self.parent.get_selected_files():
            self.parent.close_file(item)


if __name__ == '__main__':
    # QtCore.QCoreApplication.setAttribute(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    # main_window.showMaximized()  # 屏幕最大化显示窗口
    app.exec()
