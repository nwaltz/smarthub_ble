# from https://github.com/MenxLi/tkSliderWidget
# BSD-2 license

from tkinter import *
from tkinter.ttk import *

from tkinter import font
from typing import TypedDict, List, Callable, Optional, Union

class Bar(TypedDict):
    Ids: List[int]
    Pos: float
    Value: float

num_t = Union[int, float]
class Slider(Frame):
    LINE_COLOR = "#eeeeee"
    LINE_WIDTH = 3
    BAR_COLOR_INNER = "#5489ad"
    BAR_COLOR_OUTTER = "#94c9ed"
    BAR_RADIUS = 10
    BAR_RADIUS_INNER = BAR_RADIUS - 5
    DIGIT_PRECISION = ".1f"  # for showing in the canvas

    # relative step size in 0 to 1, set to 0 for no step size restiction
    # may be override by the step_size argument in __init__
    STEP_SIZE:float = 0.0

    def __init__(
        self,
        master,
        width: int = 400,
        height: int = 80,
        min_val: num_t = 0,
        max_val: num_t = 1,
        step_size: Optional[float] = None,
        init_lis: Optional[list[num_t]] = None,
        show_value = True,
        removable = False,
        addable = False,
    ):
        if step_size == None:
            # inherit from class variable
            step_size = self.STEP_SIZE
        assert step_size >= 0, "step size must be positive"
        assert step_size <= max_val - min_val, "step size must be smaller than range"
        assert min_val < max_val, "min value must be smaller than max value"

        Frame.__init__(self, master, height=height, width=width)
        self.master = master
        if init_lis == None:
            init_lis = [min_val]
        self.init_lis = init_lis
        self.max_val = max_val
        self.min_val = min_val
        self.step_size_frac = step_size / float(max_val - min_val)  # step size fraction

        self.show_value = show_value
        self.H = height
        self.W = width
        self.canv_H = self.H
        self.canv_W = self.W
        if not show_value:
            self.slider_y = self.canv_H / 2  # y pos of the slider
        else:
            self.slider_y = self.canv_H * 2 / 5
        self.slider_x = Slider.BAR_RADIUS  # x pos of the slider (left side)

        self._val_change_callback = lambda lis: None

        self.bars: List[Bar] = []
        self.selected_idx = None  # current selection bar index
        for value in self.init_lis:
            pos = (value - min_val) / (max_val - min_val)
            ids = []
            bar: Bar = {"Pos": pos, "Ids": ids, "Value": value}
            self.bars.append(bar)

        self.canv = Canvas(self, height=self.canv_H, width=self.canv_W)
        self.canv.pack()
        self.canv.bind("<Motion>", self._mouseMotion)
        self.canv.bind("<B1-Motion>", self._moveBar)
        if removable:
            self.canv.bind("<3>", self._removeBar)
        if addable:
            self.canv.bind("<ButtonRelease-1>", self._addBar)

        self.__addTrack(
            self.slider_x, self.slider_y, self.canv_W - self.slider_x, self.slider_y
        )
        for bar in self.bars:
            bar["Ids"] = self.__addBar(bar["Pos"])

    def getValues(self) -> List[float]:
        values = [bar["Value"] for bar in self.bars]
        return sorted(values)
    
    def setValueChangeCallback(self, callback: Callable[[List[float]], None]):
        self._val_change_callback = callback

    def _mouseMotion(self, event):
        x = event.x
        y = event.y
        selection = self.__checkSelection(x, y)
        if selection[0]:
            self.canv.config(cursor="hand2")
            self.selected_idx = selection[1]
        else:
            self.canv.config(cursor="")
            self.selected_idx = None

    def _moveBar(self, event):
        x = event.x
        y = event.y
        if self.selected_idx == None:
            return False
        pos = self.__calcPos(x)
        idx = self.selected_idx
        if self.step_size_frac > 0:
            curr_pos = self.bars[idx]["Pos"]
            if abs(curr_pos - pos) < (self.step_size_frac * 0.75):
                return
            pos = round(pos / self.step_size_frac) * self.step_size_frac
        self.__moveBar(idx, pos)

    def _removeBar(self, event):
        x = event.x
        y = event.y
        if self.selected_idx == None:
            return False
        idx = self.selected_idx
        ids = self.bars[idx]["Ids"]
        for id in ids:
            self.canv.delete(id)
        self.bars.pop(idx)

    def _addBar(self, event):
        x = event.x
        y = event.y

        if self.selected_idx == None:
            pos = self.__calcPos(x)
            ids = []
            bar = {
                "Pos": pos,
                "Ids": ids,
                "Value": self.__calcPos(x) * (self.max_val - self.min_val)
                + self.min_val,
            }
            self.bars.append(bar)

            for i in self.bars:
                ids = i["Ids"]
                for id in ids:
                    self.canv.delete(id)

            for bar in self.bars:
                bar["Ids"] = self.__addBar(bar["Pos"])

    def __addTrack(self, startx, starty, endx, endy):
        id1 = self.canv.create_line(
            startx, starty, endx, endy, fill=Slider.LINE_COLOR, width=Slider.LINE_WIDTH
        )
        return id

    def __addBar(self, pos):
        """@ pos: position of the bar, ranged from (0,1)"""
        if pos < 0 or pos > 1:
            raise Exception("Pos error - Pos: " + str(pos))
        R = Slider.BAR_RADIUS
        r = Slider.BAR_RADIUS_INNER
        L = self.canv_W - 2 * self.slider_x
        y = self.slider_y
        x = self.slider_x + pos * L
        id_outer = self.canv.create_oval(
            x - R,
            y - R,
            x + R,
            y + R,
            fill=Slider.BAR_COLOR_OUTTER,
            width=2,
            outline="",
        )
        id_inner = self.canv.create_oval(
            x - r, y - r, x + r, y + r, fill=Slider.BAR_COLOR_INNER, outline=""
        )
        if self.show_value:
            y_value = y + Slider.BAR_RADIUS + 8
            value = pos * (self.max_val - self.min_val) + self.min_val
            id_value = self.canv.create_text(
                x, y_value, fill='white', text=format(value, Slider.DIGIT_PRECISION), font=font.Font(self.canv, font=("Helvetica", 10))
            )
            return [id_outer, id_inner, id_value]
        else:
            return [id_outer, id_inner]

    def __moveBar(self, idx, pos):
        ids = self.bars[idx]["Ids"]
        for id in ids:
            self.canv.delete(id)
        self.bars[idx]["Ids"] = self.__addBar(pos)
        self.bars[idx]["Pos"] = pos
        self.bars[idx]["Value"] = pos * (self.max_val - self.min_val) + self.min_val
        self._val_change_callback(self.getValues())

    def __calcPos(self, x):
        """calculate position from x coordinate"""
        pos = (x - self.slider_x) / (self.canv_W - 2 * self.slider_x)
        if pos < 0:
            return 0
        elif pos > 1:
            return 1
        else:
            return pos

    def __checkSelection(self, x, y):
        """
        To check if the position is inside the bounding rectangle of a Bar
        Return [True, bar_index] or [False, None]
        """
        for idx in range(len(self.bars)):
            id = self.bars[idx]["Ids"][0]
            bbox = self.canv.bbox(id)
            if bbox[0] < x and bbox[2] > x and bbox[1] < y and bbox[3] > y:
                return [True, idx]
        return [False, None]