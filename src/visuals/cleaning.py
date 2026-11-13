"""Plot the SQL cleaning command’s before-and-after sensor readings."""

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


def plot_sensor_readings(readings, path):
    before = readings.before_fill
    after = readings.data.reindex(before.index)
    rows = (len(before.columns) + 1) // 2
    figure = Figure(figsize=(16, 2.5 * rows), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(rows, 2, sharex=True, squeeze=False).ravel()
    for axis, sensor in zip(axes, before):
        axis.plot(
            before.index,
            before[sensor],
            color="steelblue",
            linewidth=0.8,
            label="Before fill",
        )
        if sensor in after:
            axis.plot(
                after.index,
                after[sensor],
                color="seagreen",
                linewidth=0.7,
                alpha=0.8,
                label="Prepared",
            )
        axis.set_title(sensor)
        axis.set_ylabel("Reading")
        axis.grid(alpha=0.25)
        axis.legend(loc="best", fontsize="small")
    for axis in axes[len(before.columns) - 2 : len(before.columns)]:
        axis.tick_params(labelbottom=True)
        axis.set_xlabel("Datetime")
    for axis in axes[len(before.columns) :]:
        axis.set_visible(False)
    figure.suptitle("Sensor readings before and after preparation")
    figure.savefig(path, dpi=120)
