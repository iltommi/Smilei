"""@package pycontrol
    here we check if the namelist is clean and without errors
"""

import gc 
gc.collect()

import os

def _smilei_check():
    """Do checks over the script"""
    # Verify classes were not overriden
    for CheckClassName,CheckClass in {"SmileiComponent":SmileiComponent,"Species":Species,
            "Laser":Laser,"Collisions":Collisions,"DiagProbe":DiagProbe,"DiagParticles":DiagParticles,
            "DiagScalar":DiagScalar,"DiagFields":DiagFields,"ExtField":ExtField,
            "SmileiSingleton":SmileiSingleton,"Main":Main,"Restart":Restart}.iteritems():
        try:
            if not CheckClass._verify: raise
        except:
            raise Exception("ERROR in the namelist: it seems that the name `"+CheckClassName+"` has been overriden")
    # Verify the output_dir
    if smilei_mpi_rank == 0 and output_dir:
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as exception:
                raise Exception("ERROR in the namelist: output_dir "+output_dir+" does not exists and cannot be created")
        elif not os.path.isdir(output_dir):
                raise Exception("ERROR in the namelist: output_dir "+output_dir+" exists and is not a directory")
    # Verify the restart_dir
    if len(Restart)==1 and Restart.directory:
        if not os.path.isdir(Restart.directory):
            raise Exception("ERROR in the namelist: Restart.directory "+Restart.directory+" is not a directory")
    # Verify that constant() and tconstant() were not redefined
    if not hasattr(constant, "_reserved") or not hasattr(tconstant, "_reserved"):
        raise Exception("Names `constant` and `tconstant` cannot be overriden")
    # Convert float profiles to constant() or tconstant()
    def toSpaceProfile(input):
        try   : return constant(input*1.)
        except: return input
    def toTimeProfile(input):
        try:
            input*1.
            return tconstant()
        except: return input
    for s in Species:
        s.nb_density      = toSpaceProfile(s.nb_density      )
        s.charge_density  = toSpaceProfile(s.charge_density  )
        s.n_part_per_cell = toSpaceProfile(s.n_part_per_cell )
        s.charge          = toSpaceProfile(s.charge          )
        s.mean_velocity   = [ toSpaceProfile(p) for p in s.mean_velocity ]
        s.temperature     = [ toSpaceProfile(p) for p in s.temperature   ]
    for e in ExtField:
        e.profile         = toSpaceProfile(e.profile         )
    for a in Antenna:
        a.space_profile   = toSpaceProfile(a.space_profile   )
        a.time_profile    = toTimeProfile (a.time_profile    )
    for l in Laser:
        l.chirp_profile   = toTimeProfile( l.chirp_profile )
        l.time_envelope   = toTimeProfile( l.time_envelope )
        l.space_envelope  = [ toSpaceProfile(p) for p in l.space_envelope ]
        l.phase           = [ toSpaceProfile(p) for p in l.phase          ]


# this function will be called after initialising the simulation, just before entering the time loop
# if it returns false, the code will call a Py_Finalize();
def _keep_python_running():
    for las in Laser:
        for prof in [las.time_envelope, las.chirp_profile]:
            if callable(prof) and not hasattr(prof,"profileName"): return True
    for ant in Antenna:
        prof = ant.time_profile
        if callable(prof) and not hasattr(prof,"profileName"): return True
    
    if not nspace_win_x == 0:
        return True

    return False

# Prevent creating new components (by mistake)
def _noNewComponents(cls, *args, **kwargs):
    print "Please do not create a new "+cls.__name__
    return None
SmileiComponent.__new__ = staticmethod(_noNewComponents)



