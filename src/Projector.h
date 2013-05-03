
#ifndef PROJECTOR_H
#define PROJECTOR_H

#include "PicParams.h"
#include "SmileiMPI.h"

class ElectroMagn;
class Field;
class Particle;

class Projector {
public: 
	Projector(PicParams*, SmileiMPI*){};
	virtual void operator() (ElectroMagn* champs, Particle* part, double gf) = 0;
	virtual void operator() (Field* rho, Particle* part) = 0;
private:
};

#endif

