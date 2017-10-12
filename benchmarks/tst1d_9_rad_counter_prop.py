# ______________________________________________________________________________
#
# Benchmark for the radiation in the collision of
# a GeV electron bunch with a counter-propagatin circularly polarized wave
#
# In this tests case, an electron bunch is initialized per radiation
# loss models at the same positions with an energy of 1 GeV near the right
# boundary of the box. They propagate to the left of the box where a circularly
# polarized laser plane wave is injected. This wave has an hyper-guassian
# profile of wavelength \lambda.
#
# Validation:
# - Discontinuous radiation loss
# - Continuous radiation loss
# ______________________________________________________________________________

import math

# ______________________________________________________________________________
# Main parameters

c = 299792458
electron_mass = 9.10938356e-31
electron_charge = 1.60217662e-19
lambdar = 1e-6                # Normalization wavelength
wr = 2*math.pi*c/lambdar      # Normalization frequency

l0 = 2.0*math.pi              # laser wavelength
t0 = l0                       # optical cicle
Lx = 30*l0                    # Domain length

n0 = 1e-5                     # bunch density

Tsim = 50.*t0                 # duration of the simulation
resx = 128.                   # nb of cells in one laser wavelength

dx = l0/resx                            # space step
dt  = 0.95 * dx                 		# timestep (0.95 x CFL)

start = 0                               # Laser start
fwhm = 10*t0                            # Gaussian time fwhm
duration = 50*t0                        # Laser duration
center = duration*0.5                   # Laser profile center
order = 4                               # Laser order

gamma = 1000./0.511                     # Electron bunch initial energy
v = math.sqrt(1 - 1./gamma**2)          # electron bunch initial velocity

pusher = "vay"                         # dynamic type
radiation_list = ["Monte-Carlo","corrected-Landau-Lifshitz","Niel"]  # List of radiation models
species_name_list = ["disc","cont","Niel"]            # Name of the species

# ______________________________________________________________________________
# Functions

# Density profile for inital location of the particles
def n0_(x):
        if (Lx - 10*dx < x < Lx - dx):
                return n0
        else:
                return 0.

# ______________________________________________________________________________
# Namelists

Main(
    geometry = "1Dcartesian",

    interpolation_order = 4 ,

    cell_length = [dx],
    grid_length  = [Lx],

    number_of_patches = [16],

    timestep = dt,
    simulation_time = Tsim,

    EM_boundary_conditions = [['silver-muller']],

    reference_angular_frequency_SI = wr,

    random_seed = 0

)


LaserPlanar1D(
    box_side         = "xmin",
    a0              = 100.,
    omega           = 1.,
    polarization_phi = 0.,
    ellipticity     = 1,
    time_envelope  = tgaussian(start=start,duration=duration,
                               fwhm=fwhm,
                               center=center,
                               order=order)
)

# Loop to create all the species
# One species per radiation implementations
for i,radiation in enumerate(radiation_list):

    Species(
        name = "electron_" + species_name_list[i],
        position_initialization = "centered",
        momentum_initialization = "cold",
        particles_per_cell = 10,
        c_part_max = 1.0,
        mass = 1.0,
        charge = -1.0,
        charge_density = n0_,
        mean_velocity = [-v, 0.0, 0.0],
        temperature = [0.],
        pusher = pusher,
        radiation_model = radiation,
        time_frozen = 29*t0,
        boundary_conditions = [
            ["periodic", "periodic"],
        ],
    )

RadiationReaction(
    chipa_disc_min_threshold = 1e-2
)

DiagScalar(
    every = 100,
    vars=['Ukin_electron_disc',
          'Ukin_electron_cont',
          'Ukin_electron_Niel',
          'Urad_electron_disc',
          'Urad_electron_cont',
          'Urad_electron_Niel']
)
