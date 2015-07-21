import matplotlib.pyplot as plt
from matplotlib.mlab import griddata
# from scipy.interpolate import griddata
import time
from numpy import fmax, array, amin, amax, linspace


def plot_assets(asset_dictionary):
    # The interactive plotting should be done using something like this:
    # http://stackoverflow.com/questions/458209/is-there-a-way-to-detach-matplotlib-plots-so-that-the-computation-can-continue
    # from multiprocessing import Process
    # from matplotlib.pyplot import plot, show
    #
    # def plot_graph(*args):
    #     for data in args:
    #         plot(data)
    #     show()
    #
    # p = Process(target=plot_graph, args=([1, 2, 3],))
    # p.start()
    #
    # print 'yay'
    # print 'computation continues...'
    # print 'that rocks.'
    # print 'Now lets wait for the graph be closed to continue...:'
    # p.join()

    # see https://docs.scipy.org/doc/scipy/reference/tutorial/interpolate.html
    # from scipy import interpolate

    # see http://matplotlib.org/examples/pylab_examples/griddata_demo.html

    # ####################
    # The grooming for this cell may be obtained from the following items
    # see for example: https://docs.scipy.org/doc/scipy/reference/tutorial/interpolate.html

    # ASSETS
    # asset_list:  self.asset_dictionary.keys()
    for this_asset in asset_dictionary.keys():
        #
        #  TIME (X Direction)
        #  The time vector is determined by the items from here
        time_vector = list(asset_dictionary[this_asset].keys())
        #
        #  STATE (Z Direction)
        state_vector = []
        points = [[0, 0]]
        values = [1]
        max_distance = float(0.0)
        for item in asset_dictionary[this_asset]:
            state_vector.append(asset_dictionary[this_asset][item]['state'])
            #
            #  DISTANCE (Y Direction)
            #     list(asset_dict['PS301062996'][item]['voters'].keys())

            for i, this_time in enumerate(time_vector):
                for this_distance in list(asset_dictionary[this_asset][item]['voters'].keys()):
                    points.append([this_time, this_distance])
                    values.append(asset_dictionary[this_asset][item]['state'])
                    max_distance = fmax(max_distance, this_distance)

        # Every asset will have a plot of ONT votes versus distance and time.
        # ###########################
        # DISPLAY AS DAYS FROM groom_time
        # Set the initial outage state at ON (no outage) at the minimum time and
        points[0][0] = time_vector[0] - 60
        x = (array(points)[:, 0] - asset_dictionary['groom_time']) / 60.0 / 60.0 / 24.0
        y = (array(points)[:, 1]) * 5280.0  # miles to feet conversion
        y[0] = amin(y[1:])
        points[0][1] = amin(y)
        z = values
        # define grid.
        xi = linspace(amin(x), amax(x), 20)
        yi = linspace(amin(y), amax(y), 20)
        # grid the data.
        zi = griddata(x, y, z, xi, yi, interp='linear')
        # contour the gridded data, plotting dots at the nonuniform data points.
        # cs = plt.contour(xi, yi, zi, 10, linewidths=0.5, colors='k')
        plt.contourf(xi, yi, zi, 10,
                     #  cmap=cm.rainbow
                     vmax=abs(zi).max(),
                     vmin=-abs(zi).max())
        plt.colorbar()  # draw colorbar

        # markers = array(values)
        # markers[markers > 0] = ord('r')
        # markers[markers < 1] = ord('k')
        # these_colors = map(chr, markers)
        #    size_values = 50 * array(values) + 50
        # color_values = 0.5 * array(values) + 0.5
        # color = [str(item / 1.0) for item in array(values)]
        plt.scatter(x, y,
                    marker='o',
                    s=500,  # size_values,
                    #  cmap=cm.rainbow,
                    alpha=0.5,
                    zorder=10
                    )
        # plt.scatter(x, y, marker='o', c=these_colors, s=10, zorder=10)
        # plot data points.
        # plt.scatter(x, y, marker='o', c='b', s=5, cmap=plt.cm.rainbow, zorder=10)
        plt.title('Asset: %s' % this_asset)
        plt.xlabel('Time (Days) from %s' % time.ctime(asset_dictionary['groom_time']))
        plt.ylabel('Distance (Feet)')
        plt.tight_layout()
        plt.show()

        # xi= linspace(amin(time_vector), amax(time_vector), 100)
        # yi= linspace(0.0, max_distance, 100)
        # grid_x, grid_y = mgrid[amin(time_vector):amax(time_vector):100j, 0.0:max_distance:100j]
        # grid_z2 = griddata(points[:,0], points[:,1], values, (grid_x, grid_y), method='cubic')
        # zi = griddata(array(points)[:,0], array(points)[:,1], values, xi, yi, method='linear')
        # CS = plt.contourf(xi, yi, zi, 15, cmap= plt.cm.rainbow, vmax=abs(zi).max(), vmin=-abs(zi).max())
        # plt.show()
        # plt.subplot(221)
        # plt.imshow(grid_z2.T, extent=(time_vector[0],time_vector[-1],0,max_distance), origin='lower')
        # plt.gcf().set_size_inches(6, 6)
        # plt.show()