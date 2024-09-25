import matplotlib.pyplot as plt
import numpy as np
import time

close_flag = 0

x = np.arange(0, 10)
y = np.arange(0, 10)

# to handle close event.
def handle_close(evt):
    global close_flag # should be global variable to change the outside close_flag.
    close_flag = 1
    print('Closed Figure!')


plt.ion()
fig, ax = plt.subplots()
fig.canvas.mpl_connect('close_event', handle_close) # listen to close event
line, = plt.plot(x, y)

t = 0
delta_t = 0.1
try:
    while close_flag == 0:
        if abs(t - round(t)) < 1e-5:
            print(round(t))

        x = x + delta_t
        y = y - delta_t
        line.set_data(x, y) # change the data in the line.

        ax.relim() # recompute the axes limits.
        ax.autoscale_view() # update the axes limits.

        fig.canvas.draw() # draw the figure
        fig.canvas.flush_events() # flush the GUI events for the figure.
        # plt.show(block=False)
        time.sleep(delta_t) # wait a little bit of time

        t += delta_t

        if close_flag == 1:
            break
except KeyboardInterrupt:
    pass

print('ok')
