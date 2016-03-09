#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mpl_colors
from matplotlib import cm as cmx
import fsps
from .generalTools import calcQ
from .astrodata import dopita, sdss, vanzee, kewley

c = 2.9979e18
lsun = 3.846e33
planck = 6.626e-27
pc_to_cm = 3.08568e18

def get_colors(vals, cname='CMRmap', minv=0.05, maxv=0.8, cmap=None,
               set_bad_vals=False, return_cNorm=False):
    '''
    sM = get_colors(arr, cname='jet', minv=0.0, maxv=1.0)
    sM = get_colors(arr, cmap=cubehelix.cmap())
    '''
    if cmap is None:
        cmap = plt.get_cmap(cname)
    new_cmap = mpl_colors.LinearSegmentedColormap.from_list('trunc({0}, {1:.2f}, {2:.2f})'.format(cmap.name, minv, maxv), cmap(np.linspace(minv, maxv, 100)))
    if set_bad_vals:
        new_cmap.set_bad('white', alpha=1.0)
    cNorm = mpl_colors.Normalize(vmin=vals.min(), vmax=vals.max())
    scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=new_cmap)
    if return_cNorm:
        return scalarMap, cNorm
    else:
        scalarMap.set_array(vals)
        return scalarMap

def sextract(text, par1=None, par2=None):
    '''
    to extract stuff from cloudy output
    '''
    if np.size(text) == 1:
        if type(par1) is int:
            str1 = text[par1::]
        elif type(par1) is str or type(par1) is unicode:
            str1 = text.split(par1)
            if len(str1) == 1:
                return ''
            else:
                str1 = str1[-1]
        else:
            str1 = text
        if type(par2) is int:
            str2 = str1[0:par2]
        elif type(par2) is str or type(par2) is unicode:
            str2 = str1.split(par2)
            if len(str2) == 1:
                return ''
            else:
                str2 = str2[0]
        else:
            str2 = str1
        return str2
    else:
        res = []
        for subtext in text:
            res1 = sextract(subtext, par1=par1, par2=par2)
            if res1 != '':
                res.append(res1)
        return res

class modObj(object):
    '''
    '''
    def __init__(self, dir_, prefix, parline, read_out=False, read_rad=False,
                 read_cont=False, use_doublet=False, **kwargs):
        '''
        this needs to be called from other class or given
        a line from a ".pars" file
        [0]modnum; [1]logZ; [2]age; [3]logU; [4]logR; [5]logQ  
        '''
        self.modnum = int(parline[0])
        self.logZ = parline[1]
        self.age = parline[2]
        self.logU = parline[3]
        self.logR = parline[4]
        self.logQ = parline[5]
        self.nH = parline[6]
        try:
            self.efrac = parline[7]
        except IndexError:
            self.efrac = -1.0
        self.logq = np.log10((10.0**self.logQ)/(np.pi*4.0*self.nH*(10.0**self.logR)**2.0))
        self.fl = '{}{}{}'.format(dir_, prefix, self.modnum)
        self.load_lines(use_doublet=use_doublet)
        if read_out:
            self._read_out()
        if read_cont:
            self._load_cont()
        if read_rad:
            self._dat = dict()
            self._init_rad()
            eles = ['H', 'He', 'C', 'N', 'O', 'S', 'Si', 'Fe']
            self.ion_names, self.n_ions, self.ion_arr = dict(), dict(), dict()
            for ele in eles:
                self._init_ele(ele)
            self._init_phys()
        return
    def load_lines(self, use_doublet=False, **kwargs):
        lines = {'Lya':1215.68,
                 'Ha':6562.50,
                 'Hb':4861.36,
                 'Hg':4340.49,
                 'Hd':4101.76,
                 'OIIIa':4959.00,
                 'OIIIb':5007.00,
                 'NIIa':6548.00,
                 'NIIb':6584.00,
                 'OII':3727.00,
                 'SIIa':6716.00,
                 'SIIb':6731.00,
                 'OI':6300.00}
        line_info = np.genfromtxt(self.fl+'.lineflux')
        lam, flu = line_info[:,0], line_info[:,1]
        for name, wav in lines.iteritems():
            matchind = np.argmin(np.abs(lam-wav))
            self.__setattr__(name, flu[matchind])
        self.HaHb = self.Ha/self.Hb
        def logify(a,b):
            return np.log10(a/b)
        def logHa(x):
            return np.log10(x/self.Ha)
        def logHb(x):
            return np.log10(x/self.Hb)
        self.log_NII_Ha = logHa(self.NIIa+self.NIIb)
        self.log_SII_Ha = logHa(self.SIIa+self.SIIb)
        self.log_OIII_Hb = logHb(self.OIIIa+self.OIIIb)
        #
        self.log_NIIa_Ha = logHa(self.NIIa)
        self.log_NIIb_Ha = logHa(self.NIIb)
        self.log_SIIa_Ha = logHa(self.SIIa)
        self.log_SIIb_Ha = logHa(self.SIIb)
        #
        self.log_OIIIa_Hb = logHb(self.OIIIa)
        self.log_OIIIb_Hb = logHb(self.OIIIb)
        #
        self.log_OIII_OII = logify(self.OIIIa+self.OIIIb, self.OII)
        self.log_OIIIa_OII = logify(self.OIIIa, self.OII)
        self.log_OIIIb_OII = logify(self.OIIIb, self.OII)
        #
        self.log_OI_Ha = logHa(self.OI)
        self.log_NII_OII = logify(self.NIIa+self.NIIb, self.OII)
        self.R23 = logHb(self.OII+self.OIIIa+self.OIIIb)
        return
    def _load_cont(self, **kwargs):
        cont_info = np.genfromtxt(self.fl+'.out_cont', skip_header=1)
        self.lam, self.nebflu = cont_info[:,0], cont_info[:,3]
        self.incflu, self.attflu = cont_info[:,1], cont_info[:,2]
        self.spec_Q = calcQ(self.lam, self.incflu*lsun, f_nu=True)
        return
    def get_fsps_spec(self, **kwargs):
        sp = fsps.StellarPopulation(zcontinuous=1)
        sp.params['logzsol'] = self.logZ
        lam, spec = sp.get_spectrum(tage=self.age*1.0e-9)
        self.__setattr__('fsps_spec', spec)
        self.__setattr__('fsps_Q', calcQ(lam, spec*lsun, f_nu=True))
        return
    def _read_f(self, key, delimiter='\t', comments=';', names=True):
        '''
        self._read_f('.rad')
        '''
        file_ = self.fl+key
        try:
            return np.genfromtxt(file_,delimiter='\t', comments=';', names=True)
        except IOError:
            return None
        
    def _init_rad(self):
        '''
        self._init_rad()
        attributes:
            n_zones
            zones 
            depth
            thickness (cm)
            radius_all (cm)
            rad_pc (pc)
            dr_all (cm)
            dv_all (cm)
            r_in (cm)
            r_out (cm)
        '''
        self._dat['rad'] = self._read_f('.rad')
        if self._dat['rad'] is not None:
            self.n_zones = self._dat['rad'].size
            self.zones = np.arange(self.n_zones)
            self.depth = self._dat['rad']['depth']
            self.thickness = self.depth[-1]
            self.radius_all = self._dat['rad']['radius']
            self.rad_pc = self.radius_all/pc_to_cm
            self.dr_all = self._dat['rad']['dr']
            self.dv_all = 4.*np.pi*self.radius_all**2*self.dr_all
            self.r_in = self.radius_all[0] - self.dr_all[0]/2.
            self.r_out = self.radius_all[-1] + self.dr_all[0]/2.
        return
    def _init_phys(self):
        '''
        self._init_phys()
        adds attributes:
            ne_all: electron density (cm^-3)
            nH_all: hydrogen density (cm^-3)
            Te: electron temperature (K)
        '''
        key = 'phys'
        self._dat[key] =  self._read_f('.phys')
        if self._dat[key] is not None:
            self.ne_all = self._dat[key]['ne']
            self.nH_all = self._dat[key]['nH']
            self.nenH = self.ne_all*self.nH_all
            self.Te = self._dat[key]['Te']
            self.ff_all = self._dat[key]['fillfac']
        return
    def _init_ele(self, key):
        '''
        keys = [H, He, C, N, O, S, Si, Fe]
        attributes:
            ion_names['C'] = C__1, C__2,...C__n
            n_ions['C'] = n
            ion_arr['C'][0] = f1, f2,...,f_r
        '''
        self._dat[key] = self._read_f('.ele_'+key)
        if self._dat[key] is not None:
            ion_names = self._dat[key].dtype.names[1:]
            n_ions = np.size(ion_names)
            ion_arr = np.zeros((n_ions, self.n_zones))
            for i, ion in enumerate(ion_names):
                ion_arr[i,:] = self._dat[key][ion]
            self.ion_names[key] = ion_names
            self.n_ions[key] = n_ions
            self.ion_arr[key] = ion_arr
        return
    
    @property
    def dvff(self):
        try:
            return self.dv_all*self.ff_all
        except:
            return None
    
    def _quiet_div(self, a, b):
        if a is None or b is None:
            to_return = None
        else:
            np.seterr(all="ignore")
            to_return = a/b
            np.seterr(all=None)
        return to_return
    
    def _vol_integ(self, a):
        if a is None or self.dvff is None:
            return None
        else:
            return (a*self.dvff).sum()
    
    def _vol_mean(self, a, b=1.):
        return self._quiet_div(self._vol_integ(a*b), self._vol_integ(b))
    
    @property
    def T0(self):
        try:
            return self._vol_mean(self.Te, self.nenH)
        except:
            return None
    
    @property
    def Tpiem(self):
       try:
           return self._vol_mean((self.Te - self.T0)**2., self.nenH) / self.T0**2
       except:
           return None
    
    def _read_out(self):
        '''
        self._read_out()
        attributes:
            dist_fact: 4 pi Rinner^2 (cm^2)
            Phi0: ionizing photon flux (s^-1 cm^-2)
            cloudyQ: Phi0 * dist_fact = Q (s-1)
            gasC, gasN, gasO: n relative to H
            DGR: dust to gas ratio
            Av_ex: extinction from extended source
            Av_pt: extinction from pt source
        '''
        filename = self.fl+'.out'
        self.out = {}
        file_ = open(filename, 'r')
        for line in file_:
            line = line.split('\n')[0]
            if line[0:8] == ' ####  1':
                self.out['###First'] = line
            elif line[0:5] == ' ###':
                self.out['###Last'] = line
            elif 'Hi-Con' in line:
                for i in range(7):
                    self.out['SED' + str(i+1)] = file_.next()
            elif line[0:15] == ' IONIZE PARMET:':
                self.out['INZ'] = line
            elif 'H :' in line:
                self.out['gascomp'] = line
            elif 'Dust to gas ratio' in line:
                self.out['dust'] = line
        file_.close()
        self.dist_fact = 4.0*np.pi*(10.0**self.logR)**2.0
        self.Phi0 = float(sextract(self.out['SED2'], 'Ion pht flx:'))
        self.cloudyQ = self.Phi0*self.dist_fact
        #self.logU_Rs = float(sextract(self.out['INZ'], 'U(sp):', 'Q(ion):'))
        self.cl_Q = float(sextract(self.out['INZ'], 'Q(ion): ', 8))
        self.gasC = float(sextract(self.out['gascomp'], 'C :', 8))
        self.gasN = float(sextract(self.out['gascomp'], 'N :', 8))
        self.gasO = float(sextract(self.out['gascomp'], 'O :', 8))
        if self.out.has_key('dust'):
            self.DGR = float(sextract(self.out['dust'], '(by mass):',',' ))
            self.Av_ex = float(sextract(self.out['dust'], 'AV(ext):', '(pnt)'))
            self.Av_pt = float(sextract(self.out['dust'], ' (pnt):'))
        return

class allmods(object):
    '''
    mods = outobj.allmods(dir, prefix, read_out=True, read_rad=False)
    '''
    def __init__(self, dir_, prefix, **kwargs):
        self.modpars = np.genfromtxt('{}{}.pars'.format(dir_, prefix))
        self.load_mods(dir_, prefix, **kwargs)
        self.set_pars()
        self.set_arrs()
        read_out = kwargs.get('read_out', False)
        read_rad = kwargs.get('read_rad', False)
        if read_out:
            self.add_arrs('gasC', 'gasN', 'gasO')
            if hasattr(self.mods[0], 'DGR'):
                self.add_arrs('DGR', 'Av_ex', 'Av_pt')
            if read_rad:
                self.add_arrs('Te')
        
    def load_mods(self, dir_, prefix, **kwargs):
        mods = []
        for par in self.modpars:
            mod = modObj(dir_, prefix, par, **kwargs)
            mods.append(mod)
        self.__setattr__('mods', mods)
        self.__setattr__('nmods', len(mods))
        return
    def set_pars(self):
        self.logZ_vals = np.unique(self.modpars[:,1])
        self.age_vals = np.unique(self.modpars[:,2])
        self.logU_vals = np.unique(self.modpars[:,3])
        self.logR_vals = np.unique(self.modpars[:,4])
        self.logQ_vals = np.unique(self.modpars[:,5])
        self.nH_vals = np.unique(self.modpars[:,6])
        try:
            self.efrac_vals = np.unique(self.modpars[:,7])
        except IndexError:
            self.efrac_vals = np.array([-1.0])
    def set_arrs(self):
        iterstrings = ['logZ', 'age', 'logU', 'logR', 'logQ', 'nH', 'efrac',
                       'log_NII_Ha','log_NIIa_Ha','log_NIIb_Ha',
                       'log_OIII_Hb','log_OIIIa_Hb','log_OIIIb_Hb',
                       'log_SII_Ha','log_SIIa_Ha','log_SIIb_Ha',
                       'HaHb', 'R23','log_NII_OII', 'log_OIII_OII']
        for i in iterstrings:
            vals = np.array([mod.__getattribute__(i) for mod in self.mods])
            self.__setattr__(i, vals)
    def add_arrs(self, *args):
        for item in args:
            try:
                vals = np.array([mod.__getattribute__(item) for mod in self.mods])
                self.__setattr__(item, vals)
            except AttributeError:
                continue
        return
    
    
    def makeBPT(self, ax=None, plot_data=True, line_ratio='NIIb',
                bpt_inds=None, axlabs=None, plt_pars={}, **kwargs):
        '''
        mo.makeBPT(ax=ax, const1='age', val1=0.5e6, const2=logR, val2=19.0,
                   const3='nH', val3=10.0)
        default line_ratio is NII_b / Ha
        line_ratio = ['NII', 'SII', 'OII', 'OI', 'R23']
        or bpt_inds=['log_OIb_Ha', 'log_OIIIb_Hb']
        '''
        if axlabs is None:
            xlabel = r'log [N II] $\lambda 6584$ / H$\alpha$'
            ylabel = r'log [O III] $\lambda 5007$ / H$\beta$'
        else:
            xlabel=axlabs[0]
            ylabel=ylabs[0]
        if bpt_inds is None:
            xlabel = r'log [N II] $\lambda 6584$ / H$\alpha$'
            ylabel = r'log [O III] $\lambda 5007$ / H$\beta$'
            bpt_inds = ['log_NIIb_Ha', 'log_OIIIb_Hb']
            if line_ratio == 'NII':
                xlabel = r'log [N II] $\lambda 6548,6584$ / H$\alpha$'
                ylabel = r'log [O III] $\lambda 4959,5007$ / H$\beta$'
                bpt_inds = ['log_NII_Ha', 'log_OIII_Hb']
            if line_ratio == 'SII':
                bpt_inds[0] = 'log_SII_Ha'
                xlabel = r'log [S II] $\lambda 6716,6731$ / H$\alpha$'
            if line_ratio == 'OI':
                bpt_inds[0] = 'log_OI_Ha'
                xlabel = r'log [O I] $\lambda 6300$ / H$\alpha$'
            if line_ratio == 'OII':
                bpt_inds = ['log_NII_OII', 'log_OIII_OII']
                ylabel = r'log [O III] $\lambda 4959,5007$ / [O II] $\lambda 3726,3727$'
                xlabel = r'log [N II] $\lambda 6548,6584$ / [O II] $\lambda 3726,3727$'
            if line_ratio == 'R23':
                bpt_inds = ['R23','log_OIII_OII']
                ylabel = r'log [O III] $\lambda 4959,5007$ / [O II] $\lambda 3726,3727$'
                xlabel = r'(log [O II] $\lambda 3726,3727$ + [O III] $\lambda 4959,5007$) / H$\beta$'
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
        pd = {'const1':'age',
              'val1':0.5e6,
              'const2':'logR',
              'val2':19.0,
              'const3':'nH',
              'val3':100.0}
        for key, val in kwargs.iteritems():
            pd[key] = val
        allvars = ['nH', 'logZ', 'logR', 'logU', 'age', 'efrac']
        [allvars.remove(x) for x in [pd['const1'], pd['const2'], pd['const3']]]
        x_name, y_name = allvars[0], allvars[1]
        grid_x = self.__getattribute__(x_name+'_vals')
        grid_y = self.__getattribute__(y_name+'_vals')
        
        cut_z = kwargs.get('cut_z', None)
        if cut_z is not None:
            logZmin= cut_z[0]
            logZmax=cut_z[1]
            if x_name == 'logZ':
                grid_x = grid_x[(grid_x >= logZmin) & (grid_x <= logZmax)]
            if y_name == 'logZ':
                grid_y = grid_y[(grid_y >= logZmin) & (grid_y <= logZmax)]
        
        use_mods = [mod for mod in self.mods
                    if (mod.__getattribute__(pd['const1']) == pd['val1'])
                    & (mod.__getattribute__(pd['const2']) == pd['val2'])
                    & (mod.__getattribute__(pd['const3']) == pd['val3'])]
        
        gshape = (len(grid_y), len(grid_x))
        X, Y = np.meshgrid(grid_x, grid_y, indexing='xy')
        Zx = np.zeros(gshape)
        Zy = np.zeros(gshape)
        nrows = gshape[0]
        ncols = gshape[1]
        for ind, val in np.ndenumerate(X):
            arr = [mod for mod in use_mods if (mod.__getattribute__(x_name) == val) & (mod.__getattribute__(y_name) == Y[ind])]
            Zx[ind] = arr[0].__getattribute__(bpt_inds[0])
            Zy[ind] = arr[0].__getattribute__(bpt_inds[1])
        if plot_data:
            vanzee.plot_bpt(plot_data, line_ratio=line_ratio, ax=ax)
            sdss.plot_bpt(plot_data, line_ratio=line_ratio, ax=ax, **plt_pars)
        ax.set_xlabel(xlabel, fontsize=16)
        ax.set_ylabel(ylabel, fontsize=16)
        for i in range(nrows):
            color = kwargs.get('color', 'k')
            lw = kwargs.get('lw', 2)
            alpha = kwargs.get('alpha', 0.95)
            if i == 0:
                par_label = kwargs.get('par_label', '__nolegend__')
                ax.plot(Zx[i,:], Zy[i,:], color=color, lw=lw,
                        alpha=alpha, label=par_label)
            else:
                ax.plot(Zx[i,:], Zy[i,:], color=color, lw=lw, alpha=alpha,
                        label='__nolegend__')
        row_labs = [(Zx[i,0], Zy[i,0], '{0:.1f}'.format(float(np.unique(Y[i,:])))) for i in range(gshape[0])]
        for i in range(ncols):
            ax.plot(Zx[:,i], Zy[:,i], color=color, lw=lw, alpha=alpha,
                    label='__nolegend__')
        col_labs = [(Zx[0, i], Zy[0, i], '{0:.1f}'.format(float(np.unique(X[:,i])))) for i in range(gshape[1])]
        
        var_label = kwargs.get('var_label', '__nolegend__')
        if var_label:
            for lab in col_labs:
                ax.annotate(lab[-1],
                            xy=(lab[0], lab[1]), xycoords='data',
                            xytext=(0, -10), textcoords='offset points',
                            size=22,
                            horizontalalignment='left',
                            verticalalignment='top')
            ax.annotate(r'log Z/Z$_{\odot}$',
                        xy=(col_labs[2][0], col_labs[2][1]),
                        xycoords='data', xytext=(0, -50),
                        textcoords='offset points', size=22,
                        horizontalalignment='left',
                        verticalalignment='top')
            for lab in row_labs:
                ax.annotate(lab[-1],
                            xy=(lab[0], lab[1]), xycoords='data',
                            xytext=(-10, 0), textcoords='offset points',
                            size=22,
                            horizontalalignment='right',
                            verticalalignment='bottom')
            ax.annotate(r'log U$_0$',
                        xy=(row_labs[1][0], row_labs[1][1]),
                        xycoords='data', xytext=(-50, 15),
                        textcoords='offset points', size=22,
                        horizontalalignment='right',
                        verticalalignment='bottom')
        plt.legend(numpoints=1)
        return
    def group_mods(self, xval='logZ', yval='age', zval='NIIb',
                   const='logU', cval=-2.0, make_cut=False, **kwargs):
        grid_x = self.__getattribute__(xval+'_vals')
        grid_y = self.__getattribute__(yval+'_vals')
        if make_cut:
            xlims = kwargs.get('xlims', (-1.0, 0.1))
            ylims = kwargs.get('ylims', (0.0, 10.e6))
            grid_x = grid_x[(grid_x >= xlims[0]) & (grid_x <= xlims[1])]
            grid_y = grid_y[(grid_y >= ylims[0]) & (grid_y <= ylims[1])]
        X, Y = np.meshgrid(grid_x, grid_y)
        Z = np.zeros_like(X)
        for index, x in np.ndenumerate(Z):
            mind = [i for i in range(self.nmods)
                    if (self.mods[i].__getattribute__(xval) == X[index]
                        and self.mods[i].__getattribute__(yval) == Y[index]
                        and self.mods[i].__getattribute__(const) == cval)]
            try:
                Z[index] = self.mods[mind[0]].__getattribute__(zval)
            except AttributeError:
                print('not a valid attribute.')
        if xval == 'age':
            X*=1.0e-6
        if yval == 'age':
            Y*=1.0e-6
        return X,Y,Z
    def pxl_plot(self, xval='logZ', yval='age', zval='log_OIII_Hb',
                 const='logU', cval=-2.0, ax=None, cname='CMRmap', **kwargs):
        '''
        mods.pxl_plot(xval='logZ', yval='age', zval='log_OIII_Hb',
                      const='logR', cval=18, clab='log R (cm)')
        '''
        X, Y, Z = self.group_mods(xval=xval, yval=yval, zval=zval,
                                  const=const, cval=cval, **kwargs)
        extent, aspect = calc_dim(X, Y, Z)
        calc_aspect = kwargs.get('calc_aspect', True)
        if not calc_aspect:
            aspect = 'auto'
        masked_array = np.ma.array(Z, mask=np.isnan(Z))
        cbar_arr = kwargs.get('cbar_arr', None)
        if cbar_arr is None:
            sM, cNorm = get_colors(masked_array, return_cNorm=True, set_bad_vals=True, cname=cname)
        else:
            sM, cNorm = get_colors(cbar_arr, return_cNorm=True, set_bad_vals=True, cname=cname)
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
        pf = ax.imshow(Z, norm=cNorm, interpolation='nearest', origin='lower',
                       extent=extent, aspect=aspect,
                       cmap=cname)
        xlab = kwargs.get('xlab', None)
        ylab = kwargs.get('ylab', None)
        clab = kwargs.get('clab', None)
        if xlab is None:
            xlab = xval
            ylab = yval
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        cb = plt.colorbar(pf, ax=ax)
        if clab is not None:
            cb.set_label(clab)
        plt.draw()
        return ax

def nice_lines(key):
    lines = {'ha':[6562.50, r'H\alpha', r'\lambda6563'],
             'hb':[4861.36, r'H\beta', r'\lambda4861'],
             'o3':[5007.00, r'O III', r'\lambda5007'],
             'n2':[6584.00, r'N II', r'\lambda6584'],
             'an2':[6548.00, r'N II', r'\lambda6548'],
             'ao3':[4959.00, r'O III', r'\lambda4959'],
             'o2':[3727.00, r'O II', r'\lambdalambda3726,9'],
             's2a':[6716.00, r'S II', r'\lambda6716'],
             's2b':[6731.00, r'S II', r'\lambda6731'],
             'o1':[6300, r'O I', r'\lambda6300']}
    return lines[key]

def calc_dim(X,Y,Z):
    extent = [np.min(X), np.max(X), np.min(Y), np.max(Y)]
    dx = (extent[1] - extent[0]) / float(Z.shape[1])
    dy = (extent[3] - extent[2]) / float(Z.shape[0])
    return extent, dx/dy