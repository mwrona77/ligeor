import numpy as np
import warnings
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
plt.style.use('science')
from scipy.interpolate import interp1d
import cmasher as cmr

class Ebai():
    
    def __init__(self, model=None, model_type='knn', 
                 normalize_data=True, scale_params=True, scaler = None):
        
        '''
        Initializes an EBAI model.
        
        Parameters
        ----------
        model: None or sklearn regressor instance
        model_type: str
            Specifies the type of regressor to use. One of ['knn', 'mlp']
            If 'knn', will use sklearn.neighbors.KNeighborsRegressor.
            If 'mlp', will use sklearn.neural_network.MLPRegressor.
        normalize_data: bool
            If True, will scale each light curve by the maximum observed flux.
        scale_params: bool
            If True, will scale parameters to a specified range.
        scaler: None, sklearn scaler instance
            If None, sklearn.preprocessing.MinMaxScaler() will be used.
            
        '''
        self.model = model
        self.model_type = model_type
        self.normalize_data = normalize_data
        self.scale_params = scale_params
        self.scaler = scaler
        
    def train(self, xtrain, ytrain, **kwargs):
        '''
        Trains the EBAI model.
        
        Parameters
        ----------
        xtrain: array-like
            Array of light curves to train on.
        ytrain: array-like
            Array of corresponding parameter values.
        '''
        if self.model is not None:
            warnings.warn('Re-training existing model!')
            
        if self.normalize_data:
            xtrain_scaled = np.ones(xtrain.shape)
            for i,x in enumerate(xtrain):
                xtrain_scaled[i] = x/x.max()
        else:
            xtrain_scaled = xtrain
        if self.scale_params:
            if self.scaler is None:
                warnings.warn("Default MinMaxScaler() used since scaler not provided but scale_params enabled.")
                self.scaler = MinMaxScaler()
                ytrain_scaled = self.scaler.fit_transform(ytrain)
            else:
                ytrain_scaled = self.scaler.fit_transform(ytrain)
        else:
            ytrain_scaled = ytrain

        if self.model_type == 'knn':
            self.model = KNeighborsRegressor(**kwargs)
        elif self.model_type == 'mlp':
            self.model = MLPRegressor(**kwargs)
        else:
            raise ValueError("Unrecognized model type {}. Please provide one of ['knn', 'mlp'].".format(self.model_type))
        
        self.model.fit(xtrain_scaled, ytrain_scaled)
    
    
    def predict(self, phases, fluxes, return_absolute=True, transform_data = True, phases_model = None):
        '''
        Predicts the parameters for the input light curve(s).
        
        Parameters
        ----------
        phases: array-like
            Orbital phases of the input light curve(s).
        fluxes: array-like
            Input light curve(s).
        return_absolute: bool
            If True will preform inverse_transform using the model scaler and return the absolute (unscaled) parameters.
        transform_data: bool
            If True, the input fluxes will be normalized and interpolated in the model phases.
        phases_model: array-like
            Orbital phases of the model light curves used for training. Used for interpolating the input light curve(s).
        
        
        Returns
        -------
        params_pred: predicted parameter values
        '''
        if transform_data:
            if len(fluxes.shape) == 1:
                fluxes_scaled = fluxes/fluxes.max()
                if (len(phases) != len(phases_model)) & (phases_model is not None):
                    finterp = interp1d(phases, fluxes_scaled)
                    fluxes_transform = finterp(self.phases).reshape(-1,1)
                else:
                    fluxes_transform = fluxes_scaled.reshape(-1,1)
                    
            else:
                fluxes_transform = np.zeros((len(fluxes), len(phases_model)))
                for i,xi in enumerate(fluxes):
                    fluxes_scaled = xi/xi.max()
                    if len(phases) != len(phases_model) & (phases_model is not None):
                        finterp = interp1d(phases, fluxes_scaled)
                        fluxes_transform[i] = finterp(phases_model)
                    else:
                        fluxes_transform[i] = fluxes_scaled

        else:
            fluxes_transform = fluxes
            
        params_pred = self.model.predict(fluxes_transform)
        
        if return_absolute:
            if self.scaler is not None:
                return self.scaler.inverse_transform(params_pred)
            else:
                warnings.warn("Can't find a scaler instance to perform inverse transform. Returning default output.")
                return params_pred
        else:
            return params_pred

    
    def plot_diagnostics(self, y_train, y_test, y_pred_train, y_pred_test, labels, style='scatter', savefile='', figsize=(7, 3.5)):
        '''
        Plots diagnostics of the training and test set for the EBAI model.
        
        Parameters
        ----------
        y_train: array-like
            True parameter values of the training set
        y_test: array-like
            True parameter values of the test set
        y_pred_train: array-like
            Predicted parameter values of the training set
        y_pred_test: array-like
            Predicted parameter values of the test set
        labels: array-like
            Parameter labels
        style: str
            One of 'scatter' or 'hist'.
        savefile: str
            If provided, the figures will be saved to savefile.
        figsize: tuple
            Dimensions of the figure.

        Returns
        -------
        figure
        '''
        params_len = len(labels)
        if style=='scatter':

            fig, axes = plt.subplots(nrows = 1, ncols = 2, figsize=figsize)
            yticks = []
            for i in range(params_len):
                axes[0].scatter(y_train[:,i], y_pred_train[:,i]-i, c='k', s=0.1)
                axes[0].plot(y_train[:,i], y_train[:,i]-i, 'r-')
    
                axes[1].scatter(y_test[:,i], y_pred_test[:,i]-i, c='k', s=0.1)
                axes[1].plot(y_test[:,i], y_test[:,i]-i, 'r-')
                yticks.append(-1*i)
                
            axes[0].set_title('Training set')
            axes[1].set_title('Test set')
            axes[0].set_yticks(yticks, labels)
            axes[1].set_yticks([])
            fig.tight_layout()
            if len(savefile) != 0:
                fig.savefig(savefile)
            return fig

                
        elif style=='hist':
            ocs_train_list = []
            weights_train_list = []
            for i in range(params_len):
                ocs = np.abs((y_pred_train[:,i] - y_train[:,i])/y_train[:,i])*100
                ocs_clean = ocs[(ocs != np.inf) & (ocs < 100)]
                ocs_train_list.append(ocs_clean)
                weights_train_list.append(list(100/len(ocs_clean)*np.ones(len(ocs_clean))))
                
            ocs_test_list = []
            weights_test_list = []
            for i in range(params_len):
                ocs = np.abs((y_pred_test[:,i] - y_test[:,i])/y_test[:,i])*100
                ocs_clean = ocs[(ocs != np.inf) & (ocs < 100)]
                ocs_test_list.append(ocs_clean)
                weights_test_list.append(list(100/len(ocs_clean)*np.ones(len(ocs_clean))))

                
            colors = cmr.take_cmap_colors('cmr.lavender', params_len, cmap_range=(0.15, 0.85), return_fmt='hex')
            fig, axes = plt.subplots(nrows = 1, ncols = 2, figsize=figsize)
            
            axes[0].hist(ocs_train_list, bins=10, weights=weights_train_list, color = colors, 
                        label=[r'$i$', r'$T_{\mathrm{eff},2}/T_{\mathrm{eff},1}$', r'$FF$', r'$q$'])
            axes[0].set_xlabel('O-C differences [\%]')
            axes[0].set_ylabel('Distribution [\%]')
            axes[0].legend()
            
            axes[1].hist(ocs_train_list, bins=10, weights=weights_train_list, color = colors, 
                        label=labels)
            axes[1].set_xlabel('O-C differences [\%]')
            axes[1].legend()
            
            axes[0].set_title('Training set')
            axes[1].set_title('Test set')

            if len(savefile) != 0:
                fig.savefig(savefile)
            return fig
            
