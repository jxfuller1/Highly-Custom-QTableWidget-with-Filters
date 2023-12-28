from PyQt5.QtWidgets import QHeaderView, QPushButton, QWidget, QTableWidgetItem, QTableWidget, QApplication, \
    QVBoxLayout, QMainWindow, QComboBox, QFrame, QStyledItemDelegate, QDialog, QDialogButtonBox, QLabel, QLineEdit, \
    QProxyStyle, QListView, QCheckBox, QHBoxLayout
from PyQt5.QtCore import Qt, QRect, pyqtSlot, QMimeData, QByteArray, pyqtSignal, QEvent, QPoint, QObject, QPointF, \
    pyqtProperty
import sys
import time

from PyQt5.QtGui import QCursor, QDrag, QColor, QBrush, QFont, QPen, QPainterPath, QStandardItemModel, QStandardItem, \
    QPainter, QPolygonF, QPalette

from typing import List, Union, Tuple


# custom delegate for combo box items just to change the spacing in the combobox
class ComboCustomDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(20)  # Adjust the height as needed
        return size


class ComboBox(QComboBox):
    # emit signal whenever an item is clicked on the qcomboboxes, this is for the filtering being changed on the qtablewidget
    itemClicked = pyqtSignal(str)

    # emit a signal whenever qcombobox popup is open/closed, this is so that i can set a value in parent header class
    # that will prevent the sort & repaint of the arrow being drawn for the sort on the first mouse click in the header
    # while a qcombobox is open
    popupOpened = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.view().pressed.connect(self.handleItemPressed)
        self.setModel(QStandardItemModel(self))

        # Set a custom delegate for the view, just using it for spacing in the combobox at the moment
        delegate = ComboCustomDelegate(self)
        self.view().setItemDelegate(delegate)

        # value for keeping combo dropdown open until clicked outside of it
        self._changed = False

        self.setMouseTracking(True)

        self.view().viewport().installEventFilter(self)

    # event filter for viewport (which is the individual items in the qcombobox popup)
    # this is purely to prevent the qcomobobox from closing on doubleclicks
    def eventFilter(self, widget, event):
        if widget == self.view().viewport() and event.type() == QEvent.MouseButtonDblClick:
            self._changed = True
        return super().eventFilter(widget, event)

    # set combo popup max height based on how many items (max 15)
    def combo_dropdown_height(self, total_items):
        # set max to 15
        if total_items > 15:
            total_items = 15
        self.setMaxVisibleItems(total_items)

    def handleItemPressed(self, index):
        item = self.model().itemFromIndex(index)
        base_row = 2

        # send signal to qheaderview -> qtablewidget to filter table
        if item is not None:
            text = item.data(Qt.DisplayRole)
            self.itemClicked.emit(text)

            if text == "Show Blanks" or text == "Hide Blanks":
                base_row = 4

        # greater than 3 as i don't want to add check marks to first 2 items in the dropdown of combobox
        if item is not None and index.row() >= base_row:
            if item.checkState() == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)

        self._changed = True

    def hidePopup(self):
        if not self._changed:
            super(ComboBox, self).hidePopup()
        self._changed = False

    def showPopup(self):
        # get animation status for combobox, then set it to false
        # this must be done, otherwise the combobox will appear in 1 location and then snap to the custom placement
        # afterwards because of the animation effect
        oldanimation = app.isEffectEnabled(Qt.UI_AnimateCombo)
        app.setEffectEnabled(Qt.UI_AnimateCombo, False)
        super().showPopup()
        app.setEffectEnabled(Qt.UI_AnimateCombo, oldanimation)

        pos = QPoint()
        # drop down frame of combobox
        frame = self.findChild(QFrame)

        # get parent location as starting location for where to change drop down to
        parent_location = frame.parent().mapToGlobal(pos)

        # set custom combobox dropdown location
        frame.move(parent_location.x() - frame.width() + self.width(), parent_location.y() + self.height())

        self.popupOpened.emit()


class ButtonHeaderView(QHeaderView):
    onsortChange = pyqtSignal(int)
    onfilterChange = pyqtSignal(object)

    readjust_spans = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(Qt.Horizontal, parent)  # Adjust orientation to Horizontal
        self.m_buttons = []
        # this dict is to attach an index value to each button for when sections are moved around by user
        # in order to properly rearrange the comboboxes... only way i could figure out how to do this, all other methods failed
        self.m_buttons_index_attachments = {}

        self.sectionResized.connect(self.adjustPositions)
        self.sectionMoved.connect(self.onSectionMovedChanged)
        self.sectionCountChanged.connect(self.onSectionCountChanged)
        self.parent().verticalScrollBar().valueChanged.connect(self.adjustPositions)  # Adjust scrollbar connection

        # Set sorting enabled for the header
        self.setSectionsClickable(True)
        self.sortIndicatorChanged.connect(self.customSortChange)

        # var so that the first click out of combobox on the table headers won't trigger resorting of table
        self.outof_combo_popup = 0

    def customSortChange(self, logicalIndex):
        self.onsortChange.emit(logicalIndex)

    def mouseReleaseEvent(self, event):
        # this will prevent the sort & repaint of the arrow being drawn for the sort on the first mouse click in the header
        # while a qcombobox is open
        if not self.sectionsClickable():
            self.outof_combo_popup += 1
            if self.outof_combo_popup > 1:
                self.outof_combo_popup = 0
                self.setSectionsClickable(True)

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        logical_index = self.logicalIndexAt(event.pos())
        visual_index = self.visualIndex(logical_index)

        # hide combo buttons if they aren't being hovered over or show if being hovered over (NOTE THIS IS FOR THE
        # COMBO ARROW not for the combobox popup
        for button in self.m_buttons:
            if self.m_buttons.index(button) == visual_index:
                button.show()
            else:
                button.hide()

        # must keep super to inherit mousemoveevent functionality in order to keep functionality for user moving columns
        super().mouseMoveEvent(event)

    # this will prevent the sort & repaint of the arrow being drawn for the sort on the first mouse click in the header
    # while a qcombobox is open
    def first_mouse_click_outof_combo_popup(self):
        self.outof_combo_popup = 0
        self.setSectionsClickable(False)

    # reset values when sections moved
    def onSectionMovedChanged(self):

        # use this code to match m_buttons with logicalindexes, this for when user moves columns around
        # get all logical indexes as a list
        logical_indices = [self.logicalIndex(i) for i in range(self.count())]

        # reset m_button order based on logical indices
        self.m_buttons.clear()
        self.m_buttons.extend(self.m_buttons_index_attachments[i] for i in logical_indices)

        # emit to readjust the spans for the odd rows for sub_tables not to move
        self.readjust_spans.emit(logical_indices[0])

        self.adjustPositions()

    @pyqtSlot()
    # reset comboboxes when table columns change
    def onSectionCountChanged(self):
        self.m_buttons_index_attachments.clear()

        while self.m_buttons:
            button = self.m_buttons.pop()
            button.deleteLater()
        for i in range(self.count()):
            # Draw button in header
            button = ComboBox(self)
            button.popupOpened.connect(self.first_mouse_click_outof_combo_popup)

            # focus policy removes the box that shows current selection
            button.setFocusPolicy(Qt.NoFocus)

            button.setStyleSheet("background-color: lightgrey;")
            button.activated.connect(self.handleComboboxItemClicked)
            button.hide()

            self.adjustDropdownWidth(button)
            self.m_buttons.append(button)
            self.m_buttons_index_attachments[i] = button
            self.update_data()
            self.adjustPositions()

        self.populate_filter_dropdown()

    def handleComboboxItemClicked(self):
        self.onfilterChange.emit(self.sender())

    def check_if_parent_cell_is_widget(self, row: int, column: int) -> Union[None, str]:
        item = None
        widget = self.parent().cellWidget(row, column)

        if widget:
            # check for checkbox
            for child_widget in widget.findChildren(QWidget):
                if isinstance(child_widget, QCheckBox):
                    state = child_widget.checkState()
                    if state == 2:
                        item = "True"
                    elif state == 0:
                        item = "False"
        return item

    def populate_filter_dropdown(self):
        for column, button in enumerate(self.m_buttons):
            button.clear()

            widget_string = None
            base_index = 2
            items = set()  # Using a set to store unique items
            for row in range(self.model().rowCount()):

                if row % 2 == 0:
                    # need to use visual indexes and not logical indexes to populate based on visuals of table
                    # so the qcomobox drop down matches the visual column
                    visual_column = self.logicalIndex(column)
                    index = self.model().index(row, visual_column)
                    data = self.model().data(index, Qt.DisplayRole)

                    if data:
                        # don't add to filter just text with spaces
                        if data.strip() != "":
                            items.add(data)
                    if not data:
                        widget_string = self.check_if_parent_cell_is_widget(row, visual_column)
                        if widget_string:
                            items.add(widget_string)

            # Convert set to a list and add items to the QComboBox
            item_to_list = list(items)
            item_to_list.sort()

            button.addItem("All")
            button.addItem("Clear")

            if widget_string is None:
                button.addItem("Show Blanks")
                button.addItem("Hide Blanks")
                base_index = 4

            for index, combo_item in enumerate(item_to_list):
                button.addItem(combo_item)
                # note the index +2 (or 3) due to adding all/clear that i dont' want checkmarks on
                item = button.model().item(index + base_index, 0)
                item.setCheckState(Qt.Checked)

            button.combo_dropdown_height(len(item_to_list) + base_index)

            self.adjustDropdownWidth(button)

    # change comboxw idth based on text of the items in it
    def adjustDropdownWidth(self, combo_box):
        max_width = 0
        scrollbar_width = combo_box.view().verticalScrollBar().sizeHint().width()
        frame_width = combo_box.view().frameWidth()

        for i in range(combo_box.count()):
            width = combo_box.fontMetrics().width(combo_box.itemText(i))
            max_width = max(max_width, width)

        # set 250 for maximum width drop down
        max_dropdown_width = 250
        # padding to account for checkbox size and scrollbar
        padding = 40
        combo_box.view().setFixedWidth(min(max_width + scrollbar_width + frame_width + padding, max_dropdown_width))

    # when headers change
    def setModel(self, model):
        super().setModel(model)
        if self.model() is not None:
            self.model().headerDataChanged.connect(self.update_data)

    # when headers change
    def update_data(self):
        for i, button in enumerate(self.m_buttons):
            text = self.model().headerData(i, self.orientation(), Qt.DisplayRole)

  #  def updateGeometries(self):
 #       super().updateGeometries()
  #      self.adjustPositions()

    @pyqtSlot()
    # adjust positions for qcomboboxes due to resizing/section moves
    def adjustPositions(self):
        # adjust drop down menu location in header for when resized/column changed
        h = 0
        for index, button in enumerate(self.m_buttons):
            # note must use logical index for sectionviewposition, otherwise the qcomboboxes will NOT change position
            # when the sections are moved by the user
            logical_index = self.logicalIndex(index)
            combo_width = 19
            combo_x = self.sectionViewportPosition(logical_index) + self.sectionSize(logical_index) - combo_width - 4
            geom = QRect(
                combo_x,
                0,
                combo_width,
                20,  # Adjust width drown down arrow
            )
            button.setGeometry(geom)


class CustomTableWidget(QTableWidget):

    def __init__(self):
        super(CustomTableWidget, self).__init__()
        self.model().dataChanged.connect(self.on_cellvalue_changed)
     #   self.itemSelectionChanged.connect(self.selection_changed)
        self.cellClicked.connect(self.on_cell_clicked)
        self.setMouseTracking(True)

        self.header = ButtonHeaderView(self)
        self.setHorizontalHeader(self.header)  # Set horizontal header
        self.header.onsortChange.connect(self.sort_column_change)
        self.header.onfilterChange.connect(self.combo_filter_change)

        self.horizontalHeader().setSortIndicatorShown(True)

        self.setAlternatingRowColors(True)
        table_stylesheet = "QTableWidget {alternate-background-color: lightgray;}"
        self.setStyleSheet(table_stylesheet)

        # Set the background color of the header sections
        header_stylesheet = "QHeaderView::section { background-color: lightgrey; }"
        self.horizontalHeader().setStyleSheet(header_stylesheet)

        self.header.readjust_spans.connect(self.adjust_spans)

        self.horizontalHeader().setMaximumHeight(18)
        self.horizontalHeader().setSectionsMovable(True)

        # Set your desired background color for vertical headers using a stylesheet
        stylesheet = """
            QHeaderView::section:vertical {
                background-color: lightgray;
                border: 1px solid gray; /* Adjust the border width and color as needed */
            }, 
        """
        self.verticalHeader().setStyleSheet(stylesheet)
        self.verticalHeader().sectionClicked.connect(self.main_table_vertical_header_clicked)

    # make row below hidden or not hidden
    def main_table_vertical_header_clicked(self, row: int):
        if row % 2 == 0:
            row_hidden = self.isRowHidden(row+1)
            if row_hidden:
                self.setRowHidden(row+1, False)
                item = QTableWidgetItem("-")
                self.setVerticalHeaderItem(row, item)
            else:
                self.setRowHidden(row+1, True)
                item = QTableWidgetItem("+")
                self.setVerticalHeaderItem(row, item)

    def on_cellvalue_changed(self):
        # implementation for when user changes data in cell to repopulate header qcombobox with new data
        self.header.populate_filter_dropdown()

    def on_cell_clicked(self):
        # this is to support the header repaint/sort not being run on the first click out of qcombox popups
        if self.header.sectionsClickable() == True:
            self.header.outof_combo_popup += 1

    # this is for what index to start iterating checkbox items in the comboboxes.  The index is different depending
    # on whether column contains widgets or text because i give different options in the filters for each
    def base_index_for_combobox_filters(self, row: int = 0, column: int = 0) -> int:
        base_index = 4
        logical_index = self.horizontalHeader().logicalIndex(column)
        widget = self.cellWidget(row, logical_index)

        if widget:
            base_index = 2

        return base_index

    # activates when filter options chosen in qcomboboxes
    def combo_filter_change(self, button: QComboBox):
        # column needed
        column = self.header.m_buttons.index(button)

        base_index = self.base_index_for_combobox_filters(column=column)

        item = button.model().item(button.currentIndex())
        item_text = button.itemText(button.currentIndex())
        item_index = button.currentIndex()

        if item.checkState() == Qt.Unchecked and item_index >= base_index:
            self.hide_filter_table(item_text, column)

        if item.checkState() == Qt.Checked and item_index >= base_index:
            self.show_filter_table(item_text, column)

        # if "All" selected in combo box
        if item_index == 0:
            for index in range(base_index, button.count()):
                item = button.model().item(index)
                item.setCheckState(Qt.Checked)
                self.show_filter_table(button.itemText(index), column)
                self.show_filter_table("Show Blanks", column)

            # if all is selected in 1 of the comboboxes, MUST go back through and check the checkstates
            # of the rest of the combo boxes and re-hide anything unchecked.
            for buttons in self.header.m_buttons:
                if buttons != button:
                    column = self.header.m_buttons.index(buttons)
                    base_index = self.base_index_for_combobox_filters(column=column)

                    for index in range(base_index, buttons.count()):
                        item = buttons.model().item(index)
                        if item.checkState() == Qt.Unchecked:
                            self.hide_filter_table(buttons.itemText(index), column)
                            self.hide_filter_table("Hide Blanks", column)

        # if "Clear" selected in combo box
        if item_index == 1:
            for index in range(base_index, button.count()):
                item = button.model().item(index)
                item.setCheckState(Qt.Unchecked)
                self.hide_filter_table(button.itemText(index), column)
                self.hide_filter_table("Hide Blanks", column)

        # if "Blanks" selected in combo box for removing all blank rows
        if item_text == "Hide Blanks" and item_index == 3:
            self.hide_filter_table("Hide Blanks", column)

        # if "Blanks" selected in combo box for removing all blank rows
        if item_text == "Show Blanks" and item_index == 2:
            self.show_filter_table("Show Blanks", column)

            # if show blanks is selected in 1 of the comboboxes, MUST go back through and check the checkstates
            # of the rest of the combo boxes and re-hide anything unchecked.
            for buttons in self.header.m_buttons:
                if buttons != button:
                    column = self.header.m_buttons.index(buttons)
                    base_index = self.base_index_for_combobox_filters(column=column)
                    for index in range(base_index, buttons.count()):
                        item = buttons.model().item(index)
                        if item.checkState() == Qt.Unchecked:
                            self.hide_filter_table(buttons.itemText(index), column)
                            self.hide_filter_table("Hide Blanks", column)

    # show row based on values in column matches
    def show_filter_table(self, value, column):

        # note: "column" represents the visual column, but setrowhidden works on logicalindexes and not visual indexes,
        # so you MUST convert to the logical index if the user moves columns around
        logical_index = self.horizontalHeader().logicalIndex(column)

        for row in range(self.rowCount()):
            if row % 2 == 0:
                item = self.item(row, logical_index)

                if item:
                    item = item.text()

                # if no value, check if it's qcheckbox and get true/false string
                if not item:
                    item = self.header.check_if_parent_cell_is_widget(row, logical_index)

                if item:
                    if item == value:
                        self.setRowHidden(row, False)
                        # reset if there's a "-" in the vertical column from opening the corresponding qtablewidget row
                        vertical_item = QTableWidgetItem("+")
                        self.setVerticalHeaderItem(row, vertical_item)

                 # check if blanks selected
                if value == "Show Blanks":
                    if not item or item.strip() == "":
                        self.setRowHidden(row, False)
                        vertical_item = QTableWidgetItem("+")
                        self.setVerticalHeaderItem(row, vertical_item)

    # hide rows based on values in column matches
    def hide_filter_table(self, value, column):

        # note: "column" represents the visual column, but setrowhidden works on logicalindexes and not visual indexes,
        # so you MUST convert to the logical index if the user moves columns around
        logical_index = self.horizontalHeader().logicalIndex(column)

        for row in range(self.rowCount()):
            if row % 2 == 0:
                item = self.item(row, logical_index)

                if item:
                    item = item.text()

                # if no value, check if it's qcheckbox and get true/false string
                if not item:
                    item = self.header.check_if_parent_cell_is_widget(row, logical_index)

                if item:
                    if item == value:
                        self.setRowHidden(row, True)
                        # set row below it as hidden as that row is tied to the upper row
                        self.setRowHidden(row+1, True)

                # check if blanks selected
                if value == "Hide Blanks":
                    if not item or item.strip() == "":
                        self.setRowHidden(row, True)
                        self.setRowHidden(row+1, True)

    # return text of cell, for Qcheckboxes will return True or False as text
    def main_table_cell_item_type_text(self, row: int, col: int, item: QTableWidgetItem) -> Union[None, str]:
        # if no text in cell, check to see if it's a QWidget with a checkbox and return true or false as the text
        widget = None
        if item is None:
            widget = self.cellWidget(row, col)
            if widget is not None:
                # check for Qcheckboxes
                for child_widget in widget.findChildren(QWidget):
                    if isinstance(child_widget, QCheckBox):
                        state = child_widget.checkState()
                        if state == 2:
                            item = "True"
                        elif state == 0:
                            item = "False"
        else:
            item = item.text()

        return item

    def main_table_get_all_data(self) -> Tuple[List[List], List[List]]:
        visible_table_data = []
        hidden_table_data = []

        # get visible rows data, then hidden rows data, this is for sorting only the visible rows shown
        # if there is filters applied

        # get visible rows first
        for row in range(self.rowCount()):
            if row % 2 == 0 and not self.isRowHidden(row):
                row_data = self.main_table_get_row_data(row)
                visible_table_data.append(row_data)

        # now get hidden rows
        for row in range(self.rowCount()):
            if row % 2 == 0 and self.isRowHidden(row):
                row_data = self.main_table_get_row_data(row)
                hidden_table_data.append(row_data)

        return visible_table_data, hidden_table_data

    def main_table_get_row_data(self, row: int) -> List:
        row_data = []
        for col in range(self.columnCount()):
            item = self.item(row, col)
            text = self.main_table_cell_item_type_text(row, col, item)

            if text is not None:
                row_data.append(text)
            else:
                row_data.append("")

        # append sub table widget data in row below to be used with sorting
        row_below_widget = self.cellWidget(row+1, 0)
        sub_table_data = self.get_sub_table_data(row_below_widget)
        row_data.append(sub_table_data)

        return row_data

    def main_table_repopulate_all(self, visible_table_data: List[List], hidden_table_data: List[List]):

        # map sorted visible data back to table
        table_index = 0
        for row in range(self.rowCount()):
            if row % 2 == 0 and not self.isRowHidden(row):
                self.main_table_repopulate_row(row, visible_table_data[table_index])
                table_index +=1

        # map hidden data back to table (not sorted)
        table_index = 0
        for row in range(self.rowCount()):
            if row % 2 == 0 and self.isRowHidden(row):
                self.main_table_repopulate_row(row, hidden_table_data[table_index])
                table_index +=1

    def main_table_repopulate_row(self, row: int, table_data: List):
        # on the odd rows change sub_table data to match what was in the sub_table of the paired even column
        self.update_sub_table_on_sort(row+1, table_data[-1])
        self.update_main_table_row_height_for_subtable(row+1)

        # set all rows with the qtablewidget as hidden on sort changes... mostly so i don't have to implement
        # code to tracking which qtablewidget rows are not hidden before a sort so that the non-hidden rows
        # are in proper spots on sort changes
        self.setRowHidden(row+1, True)
        vertical_item = QTableWidgetItem("+")
        self.setVerticalHeaderItem(row, vertical_item)

        for col in range(self.columnCount()):
            #check if column has widgets with qcheckboxes
            widget = self.cellWidget(row, col)

            # if not widget in cell
            if widget is None:
                item = QTableWidgetItem(table_data[col])
                self.setItem(row, col, item)

            # if widget in cell, check for qcheckbox and set state of it, i may want to make this it's own function
            elif widget is not None:
                checkbox_widget = None
                # get the qtablewidgetitem (which is in the Qwidget)
                for child_widget in widget.findChildren(QWidget):
                    if isinstance(child_widget, QCheckBox):
                        checkbox_widget = child_widget

                if checkbox_widget is not None:
                    if table_data[col] == "True":
                        checkbox_widget.setCheckState(Qt.Checked)
                    else:
                        checkbox_widget.setCheckState(Qt.Unchecked)

    # activates when headers clicked to sort table
    def sort_column_change(self, column: int):

        sort_order = self.horizontalHeader().sortIndicatorOrder()

        visible_table_data, hidden_table_data = self.main_table_get_all_data()

        # sort visible table data
        if sort_order == 1:
            visible_table_data = sorted(visible_table_data, key=lambda x: x[column])
        elif sort_order == 0:
            visible_table_data = sorted(visible_table_data, key=lambda x: x[column], reverse=True)

        # block signals while repopulating table is faster
        self.model().blockSignals(True)
        self.main_table_repopulate_all(visible_table_data, hidden_table_data)
        self.model().blockSignals(False)

        # force a repaint after unblocking signals updates the tablewidget on screen fast
        self.viewport().repaint()

    def get_sub_table_data(self, sub_table_widget: QWidget) -> List[List]:
        table = None
        table_data = []
        # get the qtablewidget (which is in the Qwidget)
        for child_widget in sub_table_widget.findChildren(QWidget):
            if isinstance(child_widget, QTableWidget):
                table = child_widget

        for row in range(table.rowCount()):
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item is not None:
                    row_data.append(item.text())
                else:
                    row_data.append("")
            table_data.append(row_data)

        return table_data

    def update_sub_table_on_sort(self, row: int, sub_table_array: List[List]):

        current_widget = self.cellWidget(row, 0)

        old_sub_table = None
        # get the qtablewidget (which is in the Qwidget)
        for child_widget in current_widget.findChildren(QWidget):
            if isinstance(child_widget, QTableWidget):
                old_sub_table = child_widget

        old_sub_table.setRowCount(len(sub_table_array))

        # repopulate table
        if len(sub_table_array) != 0:
            for row in range(old_sub_table.rowCount()):
                for col in range(old_sub_table.columnCount()):
                    item = QTableWidgetItem(sub_table_array[row][col])
                    old_sub_table.setItem(row, col, item)

                old_sub_table.setRowHeight(row, 18)

    def update_main_table_row_height_for_subtable(self, row: int):
        current_widget = self.cellWidget(row, 0)
        height = self.get_sub_table_Height(current_widget)
        self.setRowHeight(row, height)

    # adjust spans for the rows with qtablewidgets when user moves columns, otherwise qtablewidget will move around
    def adjust_spans(self, col_reset_subtable_position: int):

        for row in range(self.rowCount()):
            if row % 2 == 1:
                current_widget = self.cellWidget(row, 0)
                # remove span and remake it: THIS IS THE ONLY WAY TO GET SUB_TABLE WIDGET for the row back into correct position
                # when user moves a column
                for column in range(self.columnCount()):
                    self.setSpan(row, column, 1, 1)

                self.setSpan(row, col_reset_subtable_position, 1, self.columnCount())

                # only reset cellwidget if the section moved into column 0 changes (visually)... otherwise
                # the connect signals gets lost for the vertical header... i don't know why
                if col_reset_subtable_position != 0:
                    self.setCellWidget(row, col_reset_subtable_position, current_widget)

    def mouseMoveEvent(self, event):
        # hide any header combobox buttons if the mouse is in the qtablewidget.  There's logic to hide comboboxes,
        # in the header class, however it only works for when mouse moves between headers, Need to have in here as well
        #, otherwise, if mouse hovering over a header to display the combobox, then moves down to the table, the combobox won't hide
        try:
            for button in self.header.m_buttons:
                button.hide()
        except:
            pass

        super().mouseMoveEvent(event)

    def make_cell_checkbox(self) -> QWidget:
        upper_widget = QWidget()
        upper_widget.setContentsMargins(0, 0, 0, 0)
        upper_layout = QVBoxLayout()
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setAlignment(Qt.AlignCenter)
        checkbox = QCheckBox("")
        checkbox.stateChanged.connect(lambda state, checkbox=checkbox: self.checkbox_value_changed(state))
        upper_layout.addWidget(checkbox)
        upper_widget.setLayout(upper_layout)
        return upper_widget

    def sub_table_create(self) -> QWidget:
        upper_widget = QWidget()
        upper_widget.setContentsMargins(30, 0, 0, 0)
        upper_layout = QVBoxLayout()
        upper_layout.setContentsMargins(0, 0, 0, 10)
        sub_table = sub_TableWidget()
        upper_layout.addWidget(sub_table)
        upper_widget.setLayout(upper_layout)
        return upper_widget

    def get_sub_table_Height(self, widget: QWidget) -> int:
        table = None
        # get the qtablewidgetitem (which is in the Qwidget)
        for child_widget in widget.findChildren(QWidget):
            if isinstance(child_widget, QTableWidget):
                table = child_widget

        total_height = table.horizontalHeader().height() + 25  # +25 to account for padding
        for row in range(table.rowCount()):
            total_height += table.rowHeight(row)
        return total_height

    # not used for anything at the moment, will be used when this is connected with a SQL database to update dateabase
    @pyqtSlot()
    def checkbox_value_changed(self, state: int):
        # get to the Qwidget item (which is the parent), as this is what i need to figure out what row it's in
        widget = self.sender().parent()
        row = self.indexAt(widget.pos()).row()
        col = self.indexAt(widget.pos()).column()

        # repopulate header filter
        self.on_cellvalue_changed()


class sub_TableWidget(QTableWidget):
    def __init__(self):
        super(sub_TableWidget, self).__init__()

        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setMaximumHeight(18)

        self.verticalHeader().sectionClicked.connect(self.sub_table_clicked)

        stylesheet = "QHeaderView::section {background-color: lightgray;} QTableWidget {alternate-background-color: lightgrey;}"
        self.setStyleSheet(stylesheet)

        self.horizontalHeader().setSectionsClickable(False)

       # new_table.horizontalHeader().setVisible(False)
       # new_table.verticalHeader().setVisible(False)

    def sub_table_clicked(self, index):
        sender = self.sender()

        # Retrieve data from the clicked row
        row_data = [sender.parent().item(index, j).text() for j in range(sender.parent().columnCount())]

        self.dlg = sub_table_window(self, sender.parent(), index, row_data)
        self.dlg.onsubtableChange.connect(self.sub_table_adjust)
        self.dlg.exec()

    def sub_table_adjust(self, table: QTableWidget, row: int, row_data: List[str]):
        for i in range(table.columnCount()):
            item = QTableWidgetItem(row_data[i])
            table.setItem(row, i, item)


class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create a table
        self.main_table = CustomTableWidget()
        self.populate_main_table()

        # this function needs to be run whenever table is populated/re-populated with data to reset
        # the items in the qcombobox headers
        self.main_table.header.onSectionCountChanged()

        # use this function to modify header labels due to overwriting qheaderview paintsection
        self.main_table.setHorizontalHeaderLabels(["Field 1", "Field 2", "Field 3", "Field N"])

        # Set vertical header labels
        for row in range(self.main_table.rowCount()):
            if row % 2 == 0:
                item = QTableWidgetItem("+")
             #   item.setBackground(QColor("#d3d3d3"))  # Set your desired background color (this doesn't seem to work on my system OS)
                self.main_table.setVerticalHeaderItem(row, item)
            else:
                item = QTableWidgetItem("")
                self.main_table.setVerticalHeaderItem(row, item)

        self.main_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.main_table)

        self.setGeometry(100, 100, 600, 400)
        self.setWindowTitle('Mouse Near Column Grid Line Example')

    def populate_main_table(self):
        self.main_table.setRowCount(1000)
        self.main_table.setColumnCount(5)

        self.main_table.model().blockSignals(True)
        start = time.time()

        # Populate the table with random data
        for row in range(self.main_table.rowCount()):

            if row % 2 == 0:
                self.main_table.setRowHeight(row, 18)
                for col in range(self.main_table.columnCount()):
                    if  col < 4 or col > 4:
                        item = QTableWidgetItem(f'Row {row}, Col {col}')
                        self.main_table.setItem(row, col, item)
                    if col == 4:
                        widget = self.main_table.make_cell_checkbox()
                        self.main_table.setCellWidget(row, col, widget)

            elif row % 2 == 1:
                self.main_table.setSpan(row, 0, 1, self.main_table.columnCount())

                sub_table = self.main_table.sub_table_create()

                self.sub_table_populate(3, 3, sub_table)
                total_height = self.main_table.get_sub_table_Height(sub_table)

                self.main_table.setRowHeight(row, total_height)
                self.main_table.setCellWidget(row, 0, sub_table)

                self.main_table.setRowHidden(row, True)

        self.main_table.model().blockSignals(False)
        end = time.time()
        print(end-start)

        # force a repaint after unblocking signals updates the tablewidget on screen fast
        self.main_table.viewport().repaint()


    def sub_table_populate(self, rows: int, columns: int, widget: QWidget):
        table = None
        # get the qtablewidgetitem (which is in the Qwidget)
        for child_widget in widget.findChildren(QWidget):
            if isinstance(child_widget, QTableWidget):
                table = child_widget

        if table is not None:
            table.setRowCount(rows)
            table.setColumnCount(columns)

            table.setHorizontalHeaderLabels(["NCR No.", "Disposition", "Extra"])

             # Populate the table with random data
            for row in range(rows):
                table.setRowHeight(row, 18)
                for col in range(columns):
                    item = QTableWidgetItem(f'sub Row {row}, sub Col {col}')
                    table.setItem(row, col, item)



# for changes values in the sub_table
class sub_table_window(QDialog):
    onsubtableChange = pyqtSignal(object, int, list)

    def __init__(self, parent, table, row, row_data):
        super(QDialog, self).__init__(parent)
        self.table = table
        self.row_data = row_data
        self.row = row

        self.initUI()

    def initUI(self):

        self.setWindowTitle("Change sub-table data?")
        self.setStyleSheet("QDialog {background-color: lightgrey;}")

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(QBtn)

        self.buttonBox.accepted.connect(self.accept_changes)
        self.buttonBox.rejected.connect(self.reject)
        self.layout = QVBoxLayout()
        self.layout.addSpacing(20)

        labels = ["NCR No.", "Disposition", "Extra"]

        for index, value in enumerate(self.row_data):
            myfont = QFont()
            myfont.setBold(True)
            label = QLabel(labels[index])
            label.setFont(myfont)
            label.setAlignment(Qt.AlignHCenter)

            line_edit = QLineEdit()
            line_edit.setText(value)

            self.layout.addWidget(label)
            self.layout.addWidget(line_edit)
            self.layout.addSpacing(20)

        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def accept_changes(self):
        all_line_edits_values = self.find_layout_children(QLineEdit)

        self.onsubtableChange.emit(self.table, self.row, all_line_edits_values)

        self.close()


    def find_layout_children(self, widget: QWidget) -> List[str]:
        widget_text = []

        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)

            # Check if the item is a widget and is of the specified type
            if item and item.widget() and isinstance(item.widget(), widget):
                widget_text.append(item.widget().text())

        return widget_text


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
