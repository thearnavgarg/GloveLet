# Author:       Joseph Tompkins
# Description:  A set of wrapper classes for NumPy arrays providing data structures used to 
#               capture a moving time series window of real-time data. 
#               The DataTimeSeries class also offers 2 types of automatic averaging of data,
#               which includes a Simple Moving Average and an Exponential Weighted Moving Average.
__all__ = ["DataTimeSeries", "DataSequence"]

import time
import numpy as np
from collections import Iterable
from scipy.signal import butter, filtfilt


class DataSequence:
    """
    Base class of DataTimeSeries.\n
    Allows for sequential access of data samples.
    Old samples are overwritten as new samples are recorded in the series.
    Does not record time deltas or time stamps. Refer to the `DataTimeSeries` class if these features are required.
    """

    def __init__(self, samples, dimensions, dtype='f'):
        self.__nsamples = samples
        self.__ndim = dimensions
        if dimensions == 1:
            self.__shape = (samples,)
        else:
            self.__shape = (samples, dimensions)
        self.__added = 0
        self.__head = 0
        # initialize data series
        self.data_series = np.zeros(self.__shape, dtype)
        self.__dtype = self.data_series.dtype

    @property
    def nsamples(self):
        return self.__nsamples

    @property
    def ndim(self):
        return self.__ndim

    @property
    def shape(self):
        return self.__shape

    @property
    def current_shape(self):
        sh = (self.added,)
        sh += self.shape[1:]
        return sh

    @property
    def head(self):
        return self.__head

    @property
    def added(self):
        return self.__added

    @property
    def dtype(self):
        return self.__dtype

    def add(self, data):
        """
        Add a data sample to the time series.\n
        If the time series is filled, the oldest value in the time series is overwritten.\t
        :param data: The data. Must be of length `ndim` dimensions. Can be any iterable.
        """
        self._increment_added()
        self._increment_head()
        self.data_series[self.head] = data

    def _increment_head(self):
        self.__head += 1
        if self.__head >= self.__nsamples:
            self.__head = 0

    def _increment_added(self):
        if self.added < self.nsamples:
            self.__added += 1

    def _get_real_index(self, from_head):
        result = self.head - from_head
        if result < 0:
            result += self.nsamples
        return result

    def __extract_range(self, start=-1, stop=-1, step=1):
        step = -step
        if stop > self.nsamples:
            shape = self.shape
        else:
            shape = (stop - start,) + self.shape[1:]
        result = np.zeros(shape, self.dtype)
        start_ind = self._get_real_index(start)
        end_ind = self._get_real_index(stop)
        if end_ind >= start_ind:
            n = start_ind + 1
            result[:n] = self.data_series[start_ind::step]
            result[n:] = self.data_series[self.nsamples:end_ind:step]
        else:
            result[:] = self.data_series[start_ind:end_ind:step]
        return result

    def __set_range(self, value, slices):
        start, stop, step = slices[0].start, slices[0].stop, slices[0].step
        if step is None or step != 1:  # TODO: Implement support for 'step' slice argument
            step = 1
        if start is None:
            start = 0
        if stop is None:
            stop = self.nsamples
        step = -step
        if stop >= self.nsamples:
            stop = self.nsamples
        start_ind = self._get_real_index(start)
        end_ind = self._get_real_index(stop)
        if end_ind >= start_ind:
            n = start_ind + 1
            if len(slices) == 2:
                self.data_series[start_ind::step, slices[1]] = value[:n]
                self.data_series[self.nsamples:end_ind:step, slices[1]] = value[n:]
            else:
                self.data_series[start_ind::step] = value[:n]
                self.data_series[self.nsamples:end_ind:step] = value[n:]
        else:
            if len(slices) == 2:
                self.data_series[start_ind:end_ind:step, slices[1]] = value[:]
            else:
                self.data_series[start_ind:end_ind:step] = value[:]

    def __setitem__(self, key, value):
        if isinstance(key, tuple) and len(key) <= 2:
            self.__set_range(value, key)
        elif isinstance(key, slice):
            self.__set_range(value, (key,))
        else:
            i = self._get_real_index(key)
            self.data_series[i] = value

    def __getitem__(self, key):
        if isinstance(key, tuple) and len(key) <= 2:
            res = self[key[0]]
            res =  res[key]
            return res
        elif isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
            if step is None or step != 1:  # TODO: Implement support for 'step' slice argument
                step = 1
            if start is None:
                start = 0
            if stop is None:
                stop = self.nsamples
            return self.__extract_range(start, stop, step)
        else:
            i = self._get_real_index(key)
            return self.data_series[i]

    def __str__(self):
        output = list()
        for i in range(self.nsamples):
            output.append(str(self[i]))
        output = '\n'.join(output)
        return output


class DataTimeSeries(DataSequence):
    """
    A class structure that simplifies recording data over time.\n
    Allows for sequential access of data samples.
    Old samples are overwritten as new samples are recorded in the series.
    Records time deltas and timestamps of samples. Use the array access operator to access
    samples in the sequential order they occurred. Negative indices are supported.
    Slicing with postive values is supported.\n
    **** Parameters ****\t
    `nsamples`: The number of data samples to retain. Once the time series is initialized with values,
    the oldest sample is overwritten each time `add` is invoked.\n
    `ndim`: the number of dimensions in a data sample\n
    Optional Parameters\t
    ___\t
    `dtype`: Sets the data type of the internal storage. Any data type accepted in a numpy array is valid.\n
    `auto_filter`: When `True`, the specified filter is applied to the data on invoking `add`. Otherwise data filters
    must be applied manually. Additionally, if `pre_filter` and `post_filter` arguments are bound to filter functions,
    these will be invoked prior to and post respectively on application of the filter specified by the `filter_alg`
    argument.\n
    `filter_alg`: The name of the built-in algorithm to use for filtering the data. Accepted values are `'ewma'`
    (Exponential Weighted Moving Average), `'sma'` (Simple Moving Average), and `None`. If `None`, no built-in filter
    will be used. Any functions bound to `pre_filter` or `post_filter` will be invoked if `auto_filter` is `True`.\n
    `pre_filter`: Binds function that accepts as its first argument a `DataTimeSeries` object, and returns
    a single altered data sample. This function is invoked before the built-in filter. Note that if no data sample
    is returned by the bound function, no effect will result. If something other than a data sample is returned,
    an error will be raised.\n
    `pre_filter`: Binds function that accepts as its first argument a `DataTimeSeries` object, and returns
    a single altered data sample. This function is invoked after the built-in filter. Note that if no data sample
    is returned by the bound function, no effect will result. If something other than a data sample is returned,
    an error will be raised.\n
    `ewma_weight`: The weight used in when calculating the EWMA of the series. If left as the default value,
    a weight will be automatically computed which is based on the number of samples currently added to the series. If
    `auto_filter` is `False` or if `filter_alg` is not `'ewma'`, this value will be ignored.\n
    Usage Examples\t
    ___\t
    \tmy_timeseries.add(data)\t
    Invoke `add` method to add a data sample to the time series.
    \t
    \tmy_timeseries[0]\t
    The above will access the most recent sample added to the time series.
    \t
    \tmy_timeseries[-1]\t
    The above will access the oldest available sample added to the time series.
    """

    def __init__(self, nsamples, ndim, dtype='f',
                 auto_filter=False, filter_alg='ewma',
                 pre_filter=None, post_filter=None, ewma_weight=None):
        """
        Constructs a `DataTimeSeries` object.\n
        **** Parameters ****\t
        :param nsamples: The number of data samples to retain. Once the time series is initialized with values,
        the oldest sample is overwritten each time `add` is invoked.\t
        :param ndim: the number of dimensions in a data sample\n
        Optional Parameters\t
        ___\t
        :param dtype: Sets the data type of the internal storage. Any data type accepted in a numpy array is valid.\t
        :param auto_filter: When `True`, the specified filter is applied to the data on invoking `add`. Otherwise data filters
        must be applied manually. Additionally, if `pre_filter` and `post_filter` arguments are bound to filter functions,
        these will be invoked prior to and post respectively on application of the filter specified by the `filter_alg`
        argument.\t
        :param filter_alg: The name of the built-in algorithm to use for filtering the data. Accepted values are `'ewma'`
        (Exponential Weighted Moving Average), `'sma'` (Simple Moving Average), and `None`. If `None`, no built-in filter
        will be used. Any functions bound to `pre_filter` or `post_filter` will be invoked if `auto_filter` is `True`.\t
        :param pre_filter: Binds function that accepts as its first argument a `DataTimeSeries` object, and returns
        a single altered data sample. This function is invoked before the built-in filter. Note that if no data sample
        is returned by the bound function, no effect will result. If something other than a data sample is returned,
        an error will be raised.\t
        :param pre_filter: Binds function that accepts as its first argument a `DataTimeSeries` object, and returns
        a single altered data sample. This function is invoked after the built-in filter. Note that if no data sample
        is returned by the bound function, no effect will result. If something other than a data sample is returned,
        an error will be raised.\t
        :param ewma_weight: The weight used in when calculating the EWMA of the series. If left as the default value,
        a weight will be automatically computed which is based on the number of samples currently added to the series. If
        `auto_filter` is `False` or if `filter_alg` is not `'ewma'`, this value will be ignored.
        """
        super().__init__(nsamples, ndim, dtype)
        self.__exp_weights = np.zeros((nsamples), 'f')
        self.__weight = ewma_weight
        self.__denom = 0.0
        self.tdelta = DataSequence(nsamples, 1)
        self.time_elapsed = DataSequence(nsamples, 1, dtype=float)
        self.timestamp = DataSequence(nsamples, 1, dtype=float)
        # bind initial function for adding data to the series
        self.add = self.__initial_time_add
        self.__raw_data = np.zeros(self.shape, self.dtype)
        # initialize data series
        self.data_series = self.__raw_data   # use raw data if not auto-filtered.
        self.__filtered_data = None
        if auto_filter:
            self.__filtered_data = np.zeros(self.shape, self.dtype)
            self.data_series = self.__filtered_data  # use filtered data if auto-filtered.
            # bind auto-filter function
            if filter_alg == 'ewma':
                self.__filter = self.ewma
            elif filter_alg == 'sma':
                self.__filter['sma'] = self.sma
            elif filter_alg == 'lowpass':
                self.__filter = self.__pass_filter # TODO: Finish implementing lowpass filter
            elif filter_alg is None:
                self.__filter = self.__pass_filter
            # bind pre-filter and post-filter callback
            self.pre_filter = pre_filter
            self.post_filter = post_filter

    def add(self, data, timestamp=None, tdelta=None, time_elapsed=None, pre_args=(), post_args=()):
        """
        Add a data sample to the time series.\n
        If the time series is filled, the oldest value in the time series is overwritten.\t
        :param data:      The data to insert into the series. Can be any iterable of length `ndim` dimensions.\t
        :param timestamp: *optional* specify the timestamp of this data sample\t
        :param pre_args: tuple of arguments to pass to `pre_filter` callable\t
        :param post_args: tuple of arguments to pass to `post_filter` callable\t
        """
        # NOTE: `add` is rebound at DataTimeSeries object creation
        pass

    def ewma(self):
        """
        Calculate the Exponential Weighted Moving Average over the data series.\n
        Uninitialized values will not factor into the average.
        """
        result = np.zeros((self.ndim), self.dtype)
        for i in range(self.added):
            result += (self.__exp_weights[i] * self[i])
        return result / self.__denom

    def sma(self):
        """
        Calculate the Simple Moving Average over the data series.\n
        Uninitialized values will not factor into the average.
        """
        if self.added == 0:
            return 0
        result = np.zeros(self.ndim, self.dtype)
        result = sum(self[:]) / self.added
        return result

    def __pass_filter(self):
        return self[0]

    def __compute_exponential_weights(self):
        if self.__weight is None:
            self.__weight = 1 - (2.0 / (self.added + 1))
        self.__denom = 0.0
        for i in range(self.added):
            self.__exp_weights[i] = self.__weight**(i)
            self.__denom += self.__exp_weights[i]

    def __initial_time_add(self, data, timestamp=None, tdelta=None, time_elapsed=None, pre_args=(), post_args=()):
        # bind next function for adding data to series until series is fully initialized
        self.add = self.__initialize_series_add
        self.data_series = self.__raw_data
        super().add(data)
        # calculate tdelta & add timestamp and tdelta
        if timestamp is None:
            timestamp = time.time()
        if time_elapsed is None:
            self.time_elapsed.add(0.0)
        else:
            self.time_elapsed.add(time_elapsed)
        if tdelta is None:
            self.tdelta.add(0.0)
        else:
            self.tdelta.add(tdelta)
        self.timestamp.add(timestamp)
        # pre-compute weights for EWMA algorithm
        self.__compute_exponential_weights()
        # if auto_filter was set to True at DataTimeSeries creation, the below will execute
        if self.__filtered_data is not None:
            self.__filter_data(pre_args, post_args)

    def __initialize_series_add(self, *args, **kwargs):
        """
        Repeats everytime 'add' is called until the data series has been completely initialized/filled with data,
        at which point `add` is bound to `__add` to optimize performance.
        """
        if self.added >= self.nsamples:
            # Rebind add method once series has been initialized/filled with data
            self.add = self.__add
        self.__compute_exponential_weights()
        self.__add(*args, **kwargs)

    def __add(self, data, timestamp=None, tdelta=None, time_elapsed=None, pre_args=(), post_args=()):
        """The optimized version of the `add` function."""
        self.data_series = self.__raw_data
        super().add(data)
        # calculate tdelta & add timestamp and tdelta
        if timestamp is None:
            timestamp = time.time()
        if tdelta is None:
            tdelta = timestamp - self.timestamp[0]
        if time_elapsed is None:
            time_elapsed = self.time_elapsed[0] + tdelta
        self.time_elapsed.add(time_elapsed)
        self.tdelta.add(tdelta)
        self.timestamp.add(timestamp)
        # if auto_filter was set to True at DataTimeSeries creation, the below will execute
        if self.__filtered_data is not None:
            self.__filter_data(pre_args, post_args)

    def __filter_data(self, pre_args=(), post_args=()):
        self.data_series = self.__raw_data
        if callable(self.pre_filter):
            # pre-filter callable must take DataTimeSeries and return single data record.
            self.__filtered_data[self.head] = self.pre_filter(self, *pre_args)
        self.__filtered_data[self.head] = self.__filter()
        self.data_series = self.__filtered_data
        if callable(self.post_filter):
            # post-filter callable must take DataTimeSeries and return single data record.
            self.__filtered_data[self.head] = self.post_filter(self, *post_args)

    def __str__(self):
        output = list()
        for i in range(self.nsamples):
            output.append(str(self[i]) + '  :  dt=' + str(self.tdelta[i]))
        output = '\n'.join(output)
        return output
