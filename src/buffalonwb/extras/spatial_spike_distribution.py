import os

import matplotlib.pyplot as plt
import numpy as np
import time


def get_indexes(spkts, pos_ts):
    """
    spkts : 1D array of spike times
    pos_ts : 1D array of position timestamps
    """
    start_time = time.time()
    last_idx = 0
    idxs = []
    for sp in spkts:
        idx = (np.abs(sp - pos_ts[last_idx:-1])).argmin()
        last_idx += idx
        idxs.append(last_idx)
    print("--- %s seconds ---" % (time.time() - start_time))
    return idxs


def get_indexes_fast(spkts, pos_ts):
    """
    Faster method, constrains search space in array.

    spkts : 1D array of spike times
    pos_ts : 1D array of position timestamps
    """
    start_time = time.time()

    nSamples = len(pos_ts)
    window = 50000
    last_idx = 0
    idxs = []

    # first spike
    idx = (np.abs(spkts[0] - pos_ts[last_idx:-1])).argmin()
    last_idx += idx
    idxs.append(last_idx)

    for sp in spkts[1:]:
        if (nSamples-last_idx)>window:
            idx = (np.abs(sp - pos_ts[last_idx:last_idx+window])).argmin()
        else:
            idx = (np.abs(sp - pos_ts[last_idx:-1])).argmin()
        last_idx += idx
        idxs.append(last_idx)
    print("--- %s seconds ---" % (time.time() - start_time))
    return idxs


def plot_spatial_spike_distribution(nwbfile, unit_id, save_fig=False):
    """
    Plots the spatial distribution of spikes.
    """
    spkts = nwbfile.units['spike_times'][unit_id][:]
    pos_ts = nwbfile.processing['behavior'].data_interfaces['Position'].spatial_series['SpatialSeries_position'].timestamps[:] / 1000

    idxs = get_indexes_fast(spkts, pos_ts)

    pos3 = nwbfile.processing['behavior'].data_interfaces['Position'].spatial_series['SpatialSeries_position'].data[:]
    pos = np.array([[p[0], p[2]] for p in pos3])
    nid = len(idxs)
    xr = (np.random.rand(nid)-.5)/2
    yr = (np.random.rand(nid)-.5)/2

    fig = plt.figure()
    plt.plot(pos[idxs, 0]+xr, pos[idxs, 1]+yr, '.', markersize=1, alpha=.01)
    plt.title('Unit '+str(unit_id)+',   nSpikes='+str(len(idxs)))

    if save_fig:
        fig.savefig(os.path.join('figs', 'cell_' + str(unit_id) + '.png'), facecolor='w', edgecolor='w')
