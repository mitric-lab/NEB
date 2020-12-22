#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from scipy.interpolate import splev, splrep, splder
import matplotlib.ticker as ticker
import os
from NEB import XYZ
from NEB.AtomicData import atom_names, atomic_number, bohr_to_angs, covalent_radii, hartree_to_eV

hartree_to_ev = 27.21138

class Analyse(object): 
    """
    A class for the analysis of NEB results

    Parameters
    ==========
    """ 

    def __init__(self):
        self.energy_paths = self.read_results()
        self.xvalues = np.linspace(0, 1, self.n_images)

        # create an x-array for the spline interpolation 
        # the number of points is arbitrary
        self.xv_for_splines = np.linspace(0, 1, 50)
        self.spline_energies = self.spline()
        self.plot()

    def read_results(self) -> np.ndarray: 
        """
        Read in the energies, gradients and geometries from the NEB calculations
        """
        # search for all energy and xyz files in the current directory
        xyz_files = []
        energy_files = []
        for name in os.listdir():
            if name.startswith("neb") and name.endswith(".xyz"):
                xyz_files.append(name)
            if name.startswith("path_energies") and name.endswith(".dat"):
                energy_files.append(name)
        xyz_files = sorted(xyz_files)
        energy_files = sorted(energy_files)
        assert len(energy_files) > 0 and len(xyz_files) > 0, "There are no result files"

        # read in all the energies from the path_energies_....dat files
        self.energies = []
        for file in energy_files:
            self.energies.append(np.loadtxt(file, usecols=[1]))
        # convert Hartree to eV
        self.energies = np.array(self.energies) * hartree_to_ev
        # the lowest energy will be set to zero
        self.energies -= np.min(self.energies)

        # read in all the geometries from each iteration
        self.R = []
        self.F = []
        for file in xyz_files:
            atomlists, gradients = XYZ.read_xyz_and_gradients(file)
            images = [XYZ.atomlist2vector(atomlist) for atomlist in atomlists]
            self.R.append(images)
            gradients = np.array(gradients).reshape(len(images), -1)
            self.F.append(np.linalg.norm(gradients, axis=1))
        # try to read in the tolerance level
        with open(xyz_files[0]) as f:
            try:
                f.readline()
                self.tolerance = float(f.readline().split()[-1].split("=")[-1])
                print("IT WORKS")
            except:
                self.tolerance = 0.06
        self.R = np.array(self.R) * bohr_to_angs
        self.F = np.array(self.F)
        # number of iterations, number of geometries in each iteration
        self.n_iterations, self.n_images = self.energies.shape

        assert self.n_iterations > 0 and self.n_images > 0, "There are no results"

    def spline(self):
        """
        Cubic B-spline interpolation of the energies so that we
        can plot a smooth curve and get the derivatives, that we need 
        for the tangents
        """
        spline_energies = []
        for es in self.energies:
            # get the spline representation of each NEB curve
            tck = splrep(self.xvalues, es)
            # spline the energies
            spline_energies.append(splev(self.xv_for_splines, tck))

        spline_energies = np.array(spline_energies)
        return spline_energies

    def plot(self):
        self.figure = plt.figure()
        self.figure.suptitle('Iteration {}'.format(0))

        ax = plt.axes([0.15, 0.25, 0.8, 0.65])
        # some axis styling
        for axis in ['top','bottom','left','right']:
            ax.spines[axis].set_linewidth(1.5)
        for tick in ax.xaxis.get_major_ticks():
            tick.label.set_fontsize(12)
        for tick in ax.yaxis.get_major_ticks():
            tick.label.set_fontsize(12)
        ax.xaxis.set_major_locator(ticker.MultipleLocator(0.1))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.05))
    
        # area of the slider
        slider_ax = plt.axes([0.2, 0.05, 0.7, 0.05])
    
        # inital plot
        self.curve_plot, = ax.plot(self.xv_for_splines, self.spline_energies[0], color="#5A6CD8", lw=1.5)
        
        self.t_plots = []
        for i, (x, y) in enumerate(zip(self.xvalues, self.energies[0])):
            if self.F[0, i] > self.tolerance:
                self.t_plots.append(ax.plot(x, y, "o", color="#DC6058", markersize=10)[0])
            else:
                self.t_plots.append(ax.plot(x, y, "o", color="#4FDC85", markersize=10)[0])


        # axis labels
        ax.set_xlabel('Reaction coordinate', fontsize=12)
        ax.set_ylabel(r'Energy / eV', fontsize=12)

        axcolor = 'lightblue'
        self.slider = Slider(slider_ax, 'Iteration: ', 0, self.n_iterations-1, valinit=0, valstep=1, valfmt='%i')
        
        self.slider.on_changed(self.update)
        plt.show()

    def update(self, val):
        n = int(self.slider.val)
        self.figure.suptitle('Iteration: {}'.format(n))
        for i, (x, y) in enumerate(zip(self.xvalues, self.energies[n])):
            if self.F[n, i] > self.tolerance:
                self.t_plots[i].set_ydata(y)
                self.t_plots[i].set_color("#DC6058")
            else:
                self.t_plots[i].set_ydata(y)
                self.t_plots[i].set_color("#4FDC85")

        self.curve_plot.set_ydata(self.spline_energies[n])
        #ax.autoscale_view()
        self.figure.canvas.draw_idle()



