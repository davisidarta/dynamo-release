from .utils import lhsclassic
from .moments import strat_mom
from scipy.optimize import least_squares
from scipy.stats import chi2
from .utils_kinetic import *
import warnings

nosplicing_models = [
    Deterministic_NoSplicing, 
    Moments_Nosplicing, 
    Moments_NoSwitchingNoSplicing]

def guestimate_alpha(x_data, time):
    '''Roughly estimate p0 for kinetics data.'''
    imax = np.argmax(x_data)
    alpha = x_data[imax] / time[imax]
    return alpha

def guestimate_gamma(x_data, time):
    '''Roughly estimate gamma0 with the assumption that time starts at 0 for degradation data.'''
    ga0 = np.clip(np.log(x_data[0]/(x_data[-1]+1e-6)) / time[-1], 1e-3, 1e3)
    return ga0

def guestimate_init_cond(x_data):
        '''Roughly estimate x0 for degradation data.'''
        x0 = np.clip(np.max(x_data, 1), 1e-4, np.inf)
        return x0

class kinetic_estimation:
    def __init__(self, param_ranges, x0_ranges, simulator):
        '''A general parameter estimation framework for all types of time-seris data
        Arguments
        ---------
            ranges: `numpy.ndarray`
                a n-by-2 numpy array containing the lower and upper ranges of n parameters 
                (and initial conditions if not fixed).
            simulator: class
                an instance of python class which solves ODEs. It should have properties 't' (k time points, 1d numpy array),
                'x0' (initial conditions for m species, 1d numpy array), and 'x' (solution, k-by-m array), 
                as well as two functions: integrate (numerical integration), solve (analytical method).
            x0: `numpy.ndarray`
                Initial conditions for the integrators if they are fixed.
        '''
        self.simulator = simulator

        self.ranges = []
        self.fixed_parameters = np.ones(len(param_ranges) + len(x0_ranges)) * np.nan
        for i in range(len(param_ranges)):
            if param_ranges[i][0] == param_ranges[i][1]:
                self.fixed_parameters[i] = param_ranges[i][0]
            else:
                self.ranges.append(param_ranges[i])
        self.n_tot_kin_params = len(param_ranges)   # the total number of kinetic parameters
        self.n_kin_params = len(self.ranges)    # the number of unfixed kinetic parameters

        for i in range(len(x0_ranges)):
            if x0_ranges[i][0] == x0_ranges[i][1]:
                self.fixed_parameters[i + self.n_tot_kin_params] = x0_ranges[i][0]
            else:
                self.ranges.append(x0_ranges[i]) 
        self.n_params = len(self.ranges)    # the number of unfixed parameters (including initial conditions) 

        self.popt = None
        self.cost = None

    def sample_p0(self, samples=1, method='lhs'):
        ret = np.zeros((samples, self.n_params))
        if method == 'lhs':
            ret = self._lhsclassic(samples)
            for i in range(self.n_params):
                ret[:, i] = ret[:, i] * (self.ranges[i][1] - self.ranges[i][0]) + self.ranges[i][0]
        else:
            for n in range(samples):
                for i in range(self.n_params):
                    r = np.random.rand()
                    ret[n, i] = r * (self.ranges[i][1] - self.ranges[i][0]) + self.ranges[i][0]
        return ret

    def _lhsclassic(self, samples):
        # From PyDOE
        # Generate the intervals
        #from .utils import lhsclassic
        H = lhsclassic(samples, self.n_params)

        return H

    def get_bound(self, axis):
        ret = np.zeros(self.n_params)
        for i in range(self.n_params):
            ret[i] = self.ranges[i][axis]
        return ret

    def normalize_data(self, X):
        return np.log(X + 1)
    
    def extract_data_from_simulator(self):
        return self.simulator.x.T
    
    def assemble_kin_params(self, unfixed_params):
        p = np.array(self.fixed_parameters[:self.n_tot_kin_params], copy=True)
        p[np.isnan(p)] = unfixed_params[:self.n_kin_params]
        return p

    def assemble_x0(self, unfixed_params):
        p = np.array(self.fixed_parameters[self.n_tot_kin_params:], copy=True)
        p[np.isnan(p)] = unfixed_params[self.n_kin_params:]
        return p

    def set_params(self, params):
        self.simulator.set_params(*self.assemble_kin_params(params))

    def get_opt_kin_params(self):
        if self.popt is not None:
            return self.assemble_kin_params(self.popt)
        else:
            return None

    def get_opt_x0_params(self):
        if self.popt is not None:
            return self.assemble_x0(self.popt)
        else:
            return None

    def f_lsq(self, params, t, x_data, method=None, normalize=True):
        method = self.simulator.default_method if method is None else method
        if method not in self.simulator.methods: 
            warnings.warn('The simulator does not support method \'{}\'. Using method \'{}\' instead.'.format(method, self.simulator.methods[0]))
            method = self.simulator.default_method
        self.set_params(params)
        x0 = self.assemble_x0(params)
        self.simulator.integrate(t, x0, method)
        ret = self.extract_data_from_simulator()
        ret = self.normalize_data(ret) if normalize else ret
        ret[np.isnan(ret)] = 0
        return (ret - x_data).flatten()

    def fit_lsq(self, t, x_data, p0=None, n_p0=1, bounds=None, sample_method='lhs', method=None, normalize=True):
        '''Fit time-seris data using least squares
        Arguments
        ---------
            t: `numpy.ndarray`
                a numpy array of n time points.
            x_data: `numpy.ndarray`
                a m-by-n numpy a array of m species, each having n values for the n time points.
            p0: `numpy.ndarray`
                Initial guess of parameters.

        Returns
        ---------
            popt: `numpy.ndarray`
                optimal parameters.
            cost: 'float'
                The cost function evaluated at the optimum.
        '''
        if p0 is None:
            p0 = self.sample_p0(n_p0, sample_method)
        else:
            if p0.ndim == 1:
                p0 = [p0]
            n_p0 = len(p0)

        x_data_norm = self.normalize_data(x_data) if normalize else x_data

        if bounds is None:
            bounds = (self.get_bound(0), self.get_bound(1))
        
        costs = np.zeros(n_p0)
        X = []
        for i in range(n_p0):
            ret = least_squares(lambda p: self.f_lsq(p, t, x_data_norm, method, normalize), p0[i], bounds=bounds)
            costs[i] = ret.cost
            X.append(ret.x)
        i_min = np.argmin(costs)
        self.popt = X[i_min]
        self.cost = costs[i_min]
        return self.popt, self.cost

    def export_parameters(self):
        return self.get_opt_kin_params()

    def export_model(self, reinstantiate=True):
        if reinstantiate:
            return self.simulator.__class__()
        else:
            return self.simulator

    def get_SSE(self):
        return self.cost

    def test_chi2(self, t, x_data, species=None, method='matrix', normalize=True):
        '''perform a Pearson's chi-square test. The statistics is computed as: sum_i (O_i - E_i)^2 / E_i, where O_i is the data and E_i is the model predication.

            The data can be either 1. stratified moments: 't' is an array of k distinct time points, 'x_data' is a m-by-k matrix of data, where m is the number of species.
            or 2. raw data: 't' is an array of k time points for k cells, 'x_data' is a m-by-k matrix of data, where m is the number of species. 
            Note that if the method is 'numerical', t has to monotonically increasing.

            If not all species are included in the data, use 'species' to specify the species of interest.

            Returns
            -------
            p: float
            The p-value of a one-tailed chi-square test.

            c2: float
            The chi-square statistics.

            df: integer
            Degree of freedom.
        '''
        if x_data.ndim == 1:
            x_data = x_data[None]

        self.simulator.integrate(t, method=method)
        x_model = self.simulator.x.T
        if species is not None:
            x_model = x_model[species]

        if normalize:
            scale = np.max(x_data, 1)
            x_data_norm = (x_data.T/scale).T
            x_model_norm = (x_model.T/scale).T
        else:
            x_data_norm = x_data
            x_model_norm = x_model
        c2 = np.sum((x_data_norm - x_model_norm)**2 / x_model_norm)
        #df = len(x_data.flatten()) - self.n_params - 1
        df = len(np.unique(t)) - self.n_params - 1
        p = 1 - chi2.cdf(c2, df)
        return p, c2, df

class Estimation_Degradation(kinetic_estimation):
    def __init__(self, ranges, x0, simulator):
        self.kin_param_keys = np.array(['alpha', 'gamma'])
        super().__init__(np.vstack((np.zeros(2), ranges)), x0, simulator)

    def guestimate_init_cond(self, x_data):
        return guestimate_init_cond(x_data)

    def guestimate_gamma(self, x_data, time):
        return guestimate_gamma(x_data, time)

    def get_param(self, key):
        return self.popt[np.where(self.kin_param_keys==key)[0][0]]

    def calc_half_life(self, key):
        return np.log(2)/self.get_param(key)

class Estimation_DeterministicDeg(Estimation_Degradation):
    '''An estimation class for degradation (with splicing) experiments.
        Order of species: <unspliced>, <spliced>
    '''
    def __init__(self, beta=None, gamma=None, x0=None):
        self.kin_param_keys = np.array(['alpha', 'beta', 'gamma'])
        if beta is not None and gamma is not None and x0 is not None:
            self._initialize(beta, gamma, x0)

    def _initialize(self, beta, gamma, x0):
        ranges = np.zeros((2, 2))
        ranges[0] = beta * np.ones(2) if np.isscalar(beta) else beta
        ranges[1] = gamma * np.ones(2) if np.isscalar(gamma) else gamma
        super().__init__(ranges, x0, Deterministic)

    def auto_fit(self, time, x_data, **kwargs):
        be0 = self.guestimate_gamma(x_data[0, :], time)
        ga0 = self.guestimate_gamma(x_data[0, :] + x_data[1, :], time)
        x0 = self.guestimate_init_cond(x_data)
        beta_bound = np.array([0, 1e2*be0])
        gamma_bound = np.array([0, 1e2*ga0])
        x0_bound = np.hstack((np.zeros((len(x0), 1)), 1e2*x0[None].T))
        self._initialize(beta_bound, gamma_bound, x0_bound)

        popt, cost = self.fit_lsq(time, x_data, p0=np.hstack((be0, ga0, x0)), **kwargs)
        return popt, cost

class Estimation_DeterministicDegNosp(Estimation_Degradation):
    def __init__(self, gamma=None, x0=None):
        '''An estimation class for degradation (without splicing) experiments.
        '''
        if gamma is not None and x0 is not None:
            self._initialize(gamma, x0)

    def _initialize(self, gamma, x0):
        ranges = gamma * np.ones(2) if np.isscalar(gamma) else gamma
        if np.isscalar(x0) or x0.ndim > 1:
            x0_ = x0
        else:
            x0_ = np.array([x0])
        super().__init__(ranges, x0_, Deterministic_NoSplicing())

    def auto_fit(self, time, x_data, sample_method='lhs', method=None, normalize=False):
        ga0 = self.guestimate_gamma(x_data, time)
        x0 = self.guestimate_init_cond(x_data[None])
        gamma_bound = np.array([0, 1e2*ga0])
        x0_bound = np.array([0, 1e2*x0])
        self._initialize(gamma_bound, x0_bound)

        popt, cost = self.fit_lsq(time, x_data, p0=np.hstack((ga0, x0)), 
            sample_method=sample_method, method=method, normalize=normalize)
        return popt, cost

class Estimation_MomentDeg(Estimation_DeterministicDeg):
    '''An estimation class for degradation (with splicing) experiments.
        Order of species: <unspliced>, <spliced>, <uu>, <ss>, <us>
        Order of parameters: beta, gamma
    '''
    def __init__(self, beta=None, gamma=None, x0=None, include_cov=True):
        self.kin_param_keys = np.array(['alpha', 'beta', 'gamma'])
        self.include_cov = include_cov
        if beta is not None and gamma is not None and x0 is not None:
            self._initialize(beta, gamma, x0)

    def _initialize(self, beta, gamma, x0):
        ranges = np.zeros((2, 2))
        ranges[0] = beta * np.ones(2) if np.isscalar(beta) else beta
        ranges[1] = gamma * np.ones(2) if np.isscalar(gamma) else gamma
        super().__init__(ranges, x0, Moments_NoSwitching())

    def extract_data_from_simulator(self):
        if self.include_cov:
            ret = np.zeros((5, len(self.simulator.t)))
            ret[0] = self.simulator.get_nu()
            ret[1] = self.simulator.get_nx()
            ret[2] = self.simulator.x[:, self.simulator.uu]
            ret[3] = self.simulator.x[:, self.simulator.xx]
            ret[4] = self.simulator.x[:, self.simulator.ux]
        else:
            ret = np.zeros((4, len(self.simulator.t)))
            ret[0] = self.simulator.get_nu()
            ret[1] = self.simulator.get_nx()
            ret[2] = self.simulator.x[:, self.simulator.uu]
            ret[3] = self.simulator.x[:, self.simulator.xx]
        return ret

class Estimation_MomentDegNosp(Estimation_Degradation):
    def __init__(self, gamma=None, x0=None):
        '''An estimation class for degradation (without splicing) experiments.
            Order of species: <r>, <rr>
        '''
        if gamma is not None and x0 is not None:
            self._initialize(gamma, x0)

    def _initialize(self, gamma, x0):
        ranges = gamma * np.ones(2) if np.isscalar(gamma) else gamma
        super().__init__(ranges, x0, Moments_NoSwitchingNoSplicing())

    def auto_fit(self, time, x_data, sample_method='lhs', method=None, normalize=False):
        ga0 = self.guestimate_gamma(x_data[0, :], time)
        x0 = self.guestimate_init_cond(x_data)
        gamma_bound = np.array([0, 1e2*ga0])
        x0_bound = np.hstack((np.zeros((len(x0), 1)), 1e2*x0[None].T))
        self._initialize(gamma_bound, x0_bound)

        popt, cost = self.fit_lsq(time, x_data, p0=np.hstack((ga0, x0)), 
            sample_method=sample_method, method=method, normalize=normalize)
        return popt, cost

class Estimation_MomentKin(kinetic_estimation):
    def __init__(self, a, b, alpha_a, alpha_i, beta, gamma, include_cov=False):
        '''An estimation class for kinetics experiments.
            Order of species: <unspliced>, <spliced>, <uu>, <ss>, <us>
        '''
        ranges = np.zeros((6, 2))
        ranges[0] = a * np.ones(2) if np.isscalar(a) else a
        ranges[1] = b * np.ones(2) if np.isscalar(b) else b
        ranges[2] = alpha_a * np.ones(2) if np.isscalar(alpha_a) else alpha_a
        ranges[3] = alpha_i * np.ones(2) if np.isscalar(alpha_i) else alpha_i
        ranges[4] = beta * np.ones(2) if np.isscalar(beta) else beta
        ranges[5] = gamma * np.ones(2) if np.isscalar(gamma) else gamma
        super().__init__(ranges, np.zeros((7, 2)), Moments())
        self.include_cov = include_cov

    def extract_data_from_simulator(self):
        if self.include_cov:
            ret = np.zeros((5, len(self.simulator.t)))
            ret[0] = self.simulator.get_nu()
            ret[1] = self.simulator.get_nx()
            ret[2] = self.simulator.x[:, self.simulator.uu]
            ret[3] = self.simulator.x[:, self.simulator.xx]
            ret[4] = self.simulator.x[:, self.simulator.ux]
        else:
            ret = np.zeros((4, len(self.simulator.t)))
            ret[0] = self.simulator.get_nu()
            ret[1] = self.simulator.get_nx()
            ret[2] = self.simulator.x[:, self.simulator.uu]
            ret[3] = self.simulator.x[:, self.simulator.xx]
        return ret

    def get_alpha_a(self):
        return self.popt[2]

    def get_alpha_i(self):
        return self.popt[3]

    def get_alpha(self):
        alpha = self.simulator.fbar(self.get_alpha_a(), self.get_alpha_i())
        return alpha

    def get_beta(self):
        return self.popt[4]

    def get_gamma(self):
        return self.popt[5]

    def calc_spl_half_life(self):
        return np.log(2)/self.get_beta()

    def calc_deg_half_life(self):
        return np.log(2)/self.get_gamma()

class Estimation_MomentKinNosp(kinetic_estimation):
    def __init__(self, a, b, alpha_a, alpha_i, gamma):
        '''An estimation class for kinetics experiments.
            Order of species: <r>, <rr>
        '''
        ranges = np.zeros((5, 2))
        ranges[0] = a * np.ones(2) if np.isscalar(a) else a
        ranges[1] = b * np.ones(2) if np.isscalar(b) else b
        ranges[2] = alpha_a * np.ones(2) if np.isscalar(alpha_a) else alpha_a
        ranges[3] = alpha_i * np.ones(2) if np.isscalar(alpha_i) else alpha_i
        ranges[4] = gamma * np.ones(2) if np.isscalar(gamma) else gamma
        super().__init__(ranges, np.zeros((5, 2)), Moments_Nosplicing())

    def get_alpha_a(self):
        return self.popt[2]

    def get_alpha_i(self):
        return self.popt[3]

    def get_alpha(self):
        alpha = self.simulator.fbar(self.get_alpha_a(). self.get_alpha_i())
        return alpha

    def get_gamma(self):
        return self.popt[4]

    def calc_deg_half_life(self):
        return np.log(2)/self.get_gamma()

class Estimation_DeterministicKinNosp(kinetic_estimation):
    def __init__(self, alpha, gamma, x0=0):
        '''An estimation class for kinetics (without splicing) experiments with the deterministic model.
            Order of species: <unspliced>, <spliced>
        '''
        ranges = np.zeros((2, 2))
        ranges[0] = alpha * np.ones(2) if np.isscalar(alpha) else alpha
        ranges[1] = gamma * np.ones(2) if np.isscalar(gamma) else gamma
        if np.isscalar(x0):
            x0 = np.ones((1, 2)) * x0
        super().__init__(ranges, x0, Deterministic_NoSplicing())

    def get_alpha(self):
        return self.popt[0]

    def get_gamma(self):
        return self.popt[1]

    def calc_half_life(self):
        return np.log(2)/self.get_gamma()

class Estimation_DeterministicKin(kinetic_estimation):
    def __init__(self, alpha, beta, gamma, x0=np.zeros(2)):
        '''An estimation class for kinetics experiments with the deterministic model.
            Order of species: <unspliced>, <spliced>
        '''
        ranges = np.zeros((3, 2))
        ranges[0] = alpha * np.ones(2) if np.isscalar(alpha) else alpha
        ranges[1] = beta * np.ones(2) if np.isscalar(beta) else beta
        ranges[2] = gamma * np.ones(2) if np.isscalar(gamma) else gamma

        if x0.ndim == 1:
            x0 = np.vstack((x0, x0)).T

        super().__init__(ranges, x0, Deterministic())

    def get_alpha(self):
        return self.popt[0]

    def get_beta(self):
        return self.popt[1]

    def get_gamma(self):
        return self.popt[2]

    def calc_spl_half_life(self):
        return np.log(2)/self.get_beta()

    def calc_deg_half_life(self):
        return np.log(2)/self.get_gamma()

class Mixture_KinDeg_NoSwitching(kinetic_estimation):
    def __init__(self, model1, model2, alpha=None, gamma=None, x0=None, beta=None):
        '''An estimation class with the mixture model.
            If beta is None, it is assumed that the data does not have the splicing process.
        '''
        self.model1 = model1
        self.model2 = model2
        if alpha is not None and gamma is not None:
            self._initialize(alpha, gamma, x0, beta)
    
    def _initialize(self, alpha, gamma, x0, beta=None):
        self.param_distributor = [[0, 2], [1, 2]] if type(self.model1) in nosplicing_models else [[0, 2, 3], [1, 2, 3]]
        model = MixtureModels([self.model1, self.model2], self.param_distributor)

        ranges = np.zeros((3, 2)) if beta is None else np.zeros((4, 2))
        ranges[0] = alpha
        if beta is None:
            ranges[2] = gamma
        else:
            ranges[2] = beta
            ranges[3] = gamma
        x0_ = np.vstack((np.zeros((self.model1.n_species, 2)), x0))
        super().__init__(ranges, x0_, model)

    def auto_fit(self, time, x_data, **kwargs):
        x0 = guestimate_init_cond(x_data[-self.model2.n_species:, :])
        x0_bound = np.hstack((np.zeros((len(x0), 1)), 1e2*x0[None].T))

        if type(self.model1) in nosplicing_models:
            al0 = guestimate_alpha(x_data[0, :], time)
        else:
            al0 = guestimate_alpha(x_data[0, :] + x_data[1, :], time)
        alpha_bound = np.array([0, 1e2*al0])

        if type(self.model2) in nosplicing_models:
            ga0 = guestimate_gamma(x_data[self.model1.n_species, :], time)
            p0 = np.hstack((al0, ga0, x0))
            beta_bound = None
        else:
            be0 = guestimate_gamma(x_data[self.model1.n_species, :], time)
            ga0 = guestimate_gamma(x_data[self.model1.n_species, :] + x_data[self.model1.n_species+1, :], time)
            p0 = np.hstack((al0, be0, ga0, x0))
            beta_bound = np.array([0, 1e2*be0])
        gamma_bound = np.array([0, 1e2*ga0])
        print(gamma_bound)

        self._initialize(alpha_bound, gamma_bound, x0_bound, beta_bound)

        popt, cost = self.fit_lsq(time, x_data, p0=p0, **kwargs)
        return popt, cost

    def export_model(self, reinstantiate=True):
        if reinstantiate:
            return MixtureModels([self.model1, self.model2], self.param_distributor)
        else:
            return self.simulator

class GoodnessOfFit:
    def __init__(self, simulator, params=None, x0=None):
        self.simulator = simulator
        if params is not None:
            self.simulator.set_params(*params)
        if x0 is not None:
            self.simulator.x0 = x0
        self.mean = None
        self.sigm = None
        self.pred = None

    def extract_data_from_simulator(self, species=None):
        ret = self.simulator.x.T
        if species is not None: ret = ret[species]
        return ret

    def prepare_data(self, t, x_data, species=None, method=None, normalize=True, reintegrate=True):
        if reintegrate:
            self.simulator.integrate(t, method=method)
        x_model = self.extract_data_from_simulator(species=species)
        if x_model.ndim == 1:
            x_model = x_model[None]

        if normalize:
            mean = strat_mom(x_data.T, t, np.mean)
            scale = np.max(mean, 0)
            x_data_norm, x_model_norm = self.normalize(x_data, x_model, scale)
        else:
            x_data_norm, x_model_norm = x_data, x_model
        self.mean = strat_mom(x_data_norm.T, t, np.mean)
        self.sigm = strat_mom(x_data_norm.T, t, np.std)
        self.pred = strat_mom(x_model_norm.T, t, np.mean)

    def normalize(self, x_data, x_model, scale=None):
        scale = np.max(x_data, 1) if scale is None else scale
        x_data_norm = (x_data.T/scale).T
        x_model_norm = (x_model.T/scale).T
        return x_data_norm, x_model_norm

    def calc_gaussian_likelihood(self):
        sig = np.array(self.sigm, copy=True)
        if np.any(sig==0):
            warnings.warn('Some standard deviations are 0; Set to 1 instead.')
            sig[sig==0] = 1
        err = ((self.pred - self.mean) / sig).flatten()
        ret = 1/(np.sqrt((2*np.pi)**len(err))*np.prod(sig)) * np.exp(-0.5*(err).dot(err))
        return ret

    def calc_gaussian_loglikelihood(self):
        sig = np.array(self.sigm, copy=True)
        if np.any(sig==0):
            warnings.warn('Some standard deviations are 0; Set to 1 instead.')
            sig[sig==0] = 1
        err = ((self.pred - self.mean) / sig).flatten()
        ret = -len(err)/2*np.log(2*np.pi) - np.sum(np.log(sig)) - 0.5*err.dot(err)
        return ret