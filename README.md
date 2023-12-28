This is a QTableWidget that supports advanced features using a custom QHeaderView

a)   "Expandable" rows that contain a QTableWidget      (really just hiding/showing the odd rows that have a Qtablewidget)

b)   QComboboxes in the headers for advanced filtering   (these will update automatically as data is changed in the columns)

c)   Custom Sorting that takes into account the rows with Qtablewidgets, so that the rows are always paired together.

d)   Movable sections

c)   Supports columns with QCheckboxes

d)   The sub tablewidget rows are clickable so that data can be changed on them  (the sub table widgets cells need to be non-editable, that code needs to be added still).


This was built with a manufacturing mindset for trackable work on what's been accomplished or not accomplished and for manipulation of data.   This can easily be adapted to populate from a 
SQL Query and have the checkbox states or cell value changes as they are changed send a SQL query to update the corresponding value on a SQL table.

![1](https://github.com/jxfuller1/QTableWidget-with-Filters-/assets/123666150/f1f21acd-2325-4cc4-904a-11242df400ed)


![2](https://github.com/jxfuller1/QTableWidget-with-Filters-/assets/123666150/36d266c2-d8c5-45d6-89d9-18bdf051e427)


![3](https://github.com/jxfuller1/QTableWidget-with-Filters-/assets/123666150/6e27227a-ec54-4cf1-804b-e0387a61351a)


![4](https://github.com/jxfuller1/QTableWidget-with-Filters-/assets/123666150/da18798b-90b0-4ea8-9374-0ef1c47aeba0)
