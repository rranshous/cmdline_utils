from optparse import Option, OptionValueError
from optparse import OptionParser, Values, isbasestring
import os.path
from copy import copy
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def throw_option_value_exception(f,*args,**kwargs):
    try:
        func(*args,**kwargs)
    except Exception, ex:
        raise
        raise OptionValueError(str(ex))

def exception_wrap(f):
    def exception_wrap(*args,**kwargs):
        return throw_option_value_exception(*args,**kwargs)
    return exception_wrap

def str_to_datetime(s):
    """
    code from "The other kelly yancey" blog
    ty: http://kbyanc.blogspot.com/2007/09/python-reconstructing-datetimes-from.html


    Takes a string in the format produced by calling str()
    on a python datetime object and returns a datetime
    instance that would produce that string.

    Acceptable formats are: "YYYY-MM-DD HH:MM:SS.ssssss+HH:MM",
                            "YYYY-MM-DD HH:MM:SS.ssssss",
                            "YYYY-MM-DD HH:MM:SS+HH:MM",
                            "YYYY-MM-DD HH:MM:SS"
    Where ssssss represents fractional seconds.  The timezone
    is optional and may be either positive or negative
    hours/minutes east of UTC.
    """

    try:
        from datetuil.parser import parse
        return parse(s)
    except ImportError:
        pass

    if s is None:
        return None
    # Split string in the form 2007-06-18 19:39:25.3300-07:00
    # into its constituent date/time, microseconds, and
    # timezone fields where microseconds and timezone are
    # optional.
    m = re.match(r'(.*?)(?:\.(\d+))?(([-+]\d{1,2}):(\d{2}))?$',
                 str(s))
    datestr, fractional, tzname, tzhour, tzmin = m.groups()

    # Create tzinfo object representing the timezone
    # expressed in the input string.  The names we give
    # for the timezones are lame: they are just the offset
    # from UTC (as it appeared in the input string).  We
    # handle UTC specially since it is a very common case
    # and we know its name.
    if tzname is None:
        tz = None
    else:
        tzhour, tzmin = int(tzhour), int(tzmin)
        if tzhour == tzmin == 0:
            tzname = 'UTC'
        tz = FixedOffset(timedelta(hours=tzhour,
                                   minutes=tzmin), tzname)

    # Convert the date/time field into a python datetime
    # object.
    x = datetime.strptime(datestr, "%Y-%m-%d %H:%M:%S")

    # Convert the fractional second portion into a count
    # of microseconds.
    if fractional is None:
        fractional = '0'
    fracpower = 6 - len(fractional)
    fractional = float(fractional) * (10 ** fracpower)

    # Return updated datetime object with microseconds and
    # timezone information.
    return x.replace(microsecond=int(fractional), tzinfo=tz)

# Turn a mannerly string representation of datetime
# and return an int epoch
def str_datetime_to_epoch(option,opt_str,value,parser):
    """ return back a integer epoch representation
        ( to be expressed in form such as: "YYY-MM-DD HH:MM:SS" )
        of the datetime string """
    from time import mktime
    date_time = str_to_datetime(value)
    epoch = mktime(date_time.timetuple())
    return int(epoch)

def extend_action(dest,value,values):
    value_list = value.split(',')
    values.ensure_value(dest,[]).extend(value_list)

def sublist_action(dest,value,values):
    LIST_SEPERATORS = ","
    SUBLIST_SEPERATORS = [':',',,']
    sublists = [l.split(*LIST_SEPERATORS) for l
                in value.split(*SUBLIST_SEPERATORS)]
    for l in sublists:
        values.ensure_value(dest,[]).append(l)

custom_types = {
    'abs_path':exception_wrap(os.path.abspath),
    'datetime':exception_wrap(str_to_datetime),
    'epoch':exception_wrap(str_datetime_to_epoch)
}

custom_actions = {
    'extend':extend_action,
    'sublist':sublist_action
}

class OptionEnhancer(type):
    def __new__(meta,class_name,base_classes,class_dict):
        # add our types
        class_dict['TYPES'] = Option.TYPES + tuple(custom_types.keys())
        class_dict['TYPES_CHECKER'] = copy(Option.TYPE_CHECKER)
        class_dict['TYPES_CHECKER'].update(custom_types)

        # add our actions
        key_tuple = tuple(custom_actions.keys())
        class_dict['ACTIONS'] = Option.ACTIONS + key_tuple
        class_dict['STORE_ACTIONS'] = Option.STORE_ACTIONS + key_tuple
        class_dict['TYPED_ACTIONS'] = Option.TYPED_ACTIONS + key_tuple

        return type.__new__(meta,class_name,base_classes,class_dict)

class EnhancedOption(Option,object):
    __metaclass__ = OptionEnhancer

    def take_action(self,action,dest,opt,value,values,parser):
        log.debug('take_action: %s',action)
        if action in custom_actions:
            custom_actions.get(action)(dest,value,values)
        else:
            Option.take_action(self,action,dest,opt,value,values,parser)
        log.debug('values: %s',values)


class DictValues(Values):
    def get(self,*args,**kwargs):
        return self.__getitem__(*args,**kwargs)

    def __getitem__(self,k,d=None):
        return getattr(self,k,d)

    def __contains__(self,k):
        return hasattr(self,k)

class EnhancedOptionParser(OptionParser):
    """ adds new types and actions. also lets you use
        options returned from parse_args to be accessed using get """
    def __init__(self,*args,**kwargs):
        kwargs['option_class'] = EnhancedOption
        OptionParser.__init__(self,*args,**kwargs)

    def get_default_values(self):
        """
        We want to use our Values child instead which
        creates a get and __contains__ method
        """
        if not self.process_default_values:
            return DictValues(self.values)

        defaults = self.defaults.copy()
        for option in self._get_all_options():
            default = defaults.get(option.dest)
            if isbasestring(default):
                opt_str = option.get_opt_string()
                defaults[option.dest] = option.check_value(opt_str, default)

        return DictValues(defaults)
