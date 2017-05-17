// ----------------------------------------------------------------------------
//! \file NlicsTables.h
//
//! \brief This class contains the tables and the functions to generate them
//! for the Nonlinear Inverse Compton Scattering
//
//! \details This header contains the definition of the class NlicsTables.
//! The implementation is adapted from the thesis results of M. Lobet
//! See http://www.theses.fr/2015BORD0361
// ----------------------------------------------------------------------------

#ifndef NLICSTABLES_H
#define NLICSTABLES_H

#include <iostream>
#include <fstream>
#include <vector>
#include <string>

#include "Params.h"

//----------------------------------------------------------------------------------------------------------------------
//! NlicsTables class: holds parameters, tables and functions to compute cross-sections,
//! optical depths and other useful parameters for the Compton Monte-Carlo pusher.
//----------------------------------------------------------------------------------------------------------------------
class NlicsTables
{

    public:

        //! Constructor for NlicsTables
        NlicsTables();

        //! Destructor for NlicsTables
        ~NlicsTables(){};

        //! Initialization of the parmeters for the nonlinear inverse Compton scattering
        void initParams(Params& params);

        //! Compute integration of F/chi between
        //! using Gauss-Legendre for a given chie value
        static double compute_integfochi(double chie,
                double chipmin,
                double chipmax,
                int nbit,
                double eps);

        //! Synchrotron emissivity from Ritus
        static double compute_sync_emissivity_ritus(double chie,
                double chiph,
                int nbit,
                double eps);

        //! Generate table values for Integration of F/chi: Integfochi
        void compute_integfochi_table(SmileiMPI *smpi);

        //! Write in a file table values for Integration of F/chi: Integfochi
        void output_integfochi_table();

        //! Computation of the cross-section dNph/dt
        double compute_dNphdt(double chipa,double gfpa);

        //! Computation of the function g of Erber using the Ridgers formulae
        double g_ridgers(double chipa);

        //! Computation of the continuous quantum radiated energy
        double norm_rad_energy(double chipa, double dt);

        //! Computation of the minimum photon quantum parameter for the array xip
        //! and computation of the xip array.
        void compute_xip_table(SmileiMPI *smpi);

        //! Write in a file the table xip_chiphmin and xip
        void output_xip_table();

    private:

        // ________________________________________
        // General parameters

        //! Output format of the tables
        std::string output_format;

        // _________________________________________
        // Table Integfochi

        //! Array containing tabulated values for the computation
        //! of the photon production rate dN_{\gamma}/dt
        //! (which is also the optical depth for the Monte-Carlo process).
        //! This table is the integration of the Synchrotron emissivity
        //! refers to as F over the quantum parameter Chi.
        std::vector<double > Integfochi;

        //! Minimum boundary of the table Integfochi
        double chipa_integfochi_min;

        //! Maximum boundary of the table Integfochi
        double chipa_integfochi_max;

        //! Delta chi for the table integfochi
        double delta_chipa_integfochi;

        //! Dimension of the array Integfochi
        int dim_integfochi;

        //! This variable is true if the table is computed, false if read
        bool integfochi_computed;

        // _________________________________________
        // Table chiph min for xip table

        //! Table containing the chiph min values
        //! Under this value, photon energy is
        //! considered negligible
        std::vector<double > xip_chiphmin_table;

        // _________________________________________
        // Table xip

        //! Table containing the cumulative distribution function \f$P(0 \rightarrow \chi_{\gamma})\f$
        //! that gives gives the probability for a photon emission in the range \f$[0, \chi_{\gamma}]\f$
        std::vector<double> xip_table;

        //! Minimum boundary for chipa in the table xip and xip_chiphmin
        double chipa_xip_min;

        //! Maximum boundary for chipa in the table xip and xip_chiphmin
        double chipa_xip_max;

        //! Delta for the chipa discretization  in the table xip and xip_chiphmin
        double chipa_xip_delta;

        //! Dimension of the discretized parameter chipa
        int chipa_xip_dim;

        //! Dimension of the discretized parameter chiph
        int chiph_xip_dim;

        //! xip power
        double xip_power;

        //! xip threshold
        double xip_threshold;

        //! This variable is true if the table is computed, false if read
        bool xip_computed;

        // _________________________________________
        // Factors

        //! Factor for the computation of dNphdt
        double factor_dNphdt;

        //! Factor Classical radiated power
        double factor_cla_rad_power;

        //! Fine structure constant
        const double fine_struct_cst = 7.2973525698e-3;

        //! Reduced Planck Constant (J.s)
        const double red_planck_cst = 1.054571628E-34;

        //! Electron mass
        const double electron_mass = 9.109382616e-31;

        //! Speed of light in vacuum (m/s)
        const double c_vacuum = 299792458;

        //! Normalized reduced Compton wavelength
        double norm_lambda_compton;

};

#endif