#-*- coding:utf-8 -*-
MUST = 1
SHOULD = 2
MAY = 3
constraints = {MAY: lambda x: u"%s can be delete" % x.__name__,
               SHOULD: lambda x: u"%s should be delete" % x.__name__,
               MUST: lambda x: u"%s will be delete automatically" % x.__name__}