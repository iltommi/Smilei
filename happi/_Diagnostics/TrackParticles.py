from .Diagnostic import Diagnostic
from .._Utils import *
import vtk as _vtk

class TrackParticles(Diagnostic):
	"""Class for loading a TrackParticles diagnostic"""

	def _init(self, species=None, select="", axes=[], timesteps=None, sort=True, length=None, chunksize=20000000, **kwargs):

		# If argument 'species' not provided, then print available species and leave
		if species is None:
			species = self.getTrackSpecies()
			if len(species)>0:
				self._error += "Printing available tracked species:\n"
				self._error += "-----------------------------------\n"
				self._error += "\n".join(species)
			else:
				self._error = "No tracked particles files found"
			return

		if sort not in [True, False]:
			self._error += "Argument `sort` must be `True` or `False`\n"
			return
		if not sort and select!="":
			self._error += "Cannot select particles if not sorted\n"
			return
		self._sort = sort


		# Get info from the hdf5 files + verifications
		# -------------------------------------------------------------------
		self.species  = species
		self._h5items = {}
		self._locationForTime = {}

		# If sorting allowed, then do the sorting
		if sort:
			# If the first path does not contain the ordered file (or it is incomplete), we must create it
			orderedfile = self._results_path[0]+self._os.sep+"TrackParticles_"+species+".h5"
			needsOrdering = False
			if not self._os.path.isfile(orderedfile):
				needsOrdering = True
			else:
				try:
					f = self._h5py.File(orderedfile)
					if "finished_ordering" not in f.attrs.keys():
						needsOrdering = True
				except:
					self._os.remove(orderedfile)
					needsOrdering = True
			if needsOrdering:
				disorderedfiles = self._findDisorderedFiles()
				self._orderFiles(disorderedfiles, orderedfile, chunksize)
			# Create arrays to store h5 items
			f = self._h5py.File(orderedfile)
			for prop in ["Id", "x", "y", "z", "px", "py", "pz", "q", "w", "chi",
			             "Ex", "Ey", "Ez", "Bx", "By", "Bz"]:
				if prop in f:
					self._h5items[prop] = f[prop]
			self.available_properties = list(self._h5items.keys())
			# Memorize the locations of timesteps in the files
			for it, t in enumerate(f["Times"]):
				self._locationForTime[t] = it
			self._timesteps = self._np.array(sorted(f["Times"]))
			self._alltimesteps = self._np.copy(self._timesteps)
			self.nParticles = self._h5items["Id"].shape[1]

		# If sorting not allowed, only find the available times
		else:
			disorderedfiles = self._findDisorderedFiles()
			self._timesteps = []
			for file in disorderedfiles:
				f = self._h5py.File(file)
				for it, t in enumerate(f["data"].keys()):
					self._locationForTime[int(t)] = [f, it]
					self._timesteps += [int(t)]
			self._timesteps = self._np.array(self._timesteps)
			self._alltimesteps = self._np.copy(self._timesteps)
			properties = {"id":"Id", "position/x":"x", "position/y":"y", "position/z":"z",
			              "momentum/x":"px", "momentum/y":"py", "momentum/z":"pz",
			              "charge":"q", "weight":"w", "chi":"chi",
			              "E/x":"Ex", "E/y":"Ey", "E/z":"Ez",
			              "B/x":"Bx", "B/y":"By", "B/z":"Bz"}
			T0 = next(f["data"].itervalues())["particles/"+self.species]
			self.available_properties = [v for k,v in properties.items() if k in T0]

		# Get available times in the hdf5 file
		if self._timesteps.size == 0:
			self._error = "No tracked particles found"
			return
		# If specific timesteps requested, narrow the selection
		if timesteps is not None:
			try:
				ts = self._np.array(self._np.double(timesteps),ndmin=1)
				if ts.size==2:
					# get all times in between bounds
					self._timesteps = self._timesteps[ self._np.nonzero((self._timesteps>=ts[0]) * (self._timesteps<=ts[1]))[0] ]
				elif ts.size==1:
					# get nearest time
					self._timesteps = self._np.array(self._timesteps[ self._np.array([(self._np.abs(self._timesteps-ts)).argmin()]) ])
				else:
					raise
			except:
				self._error = "Argument `timesteps` must be one or two non-negative integers"
				return
		# Need at least one timestep
		if self._timesteps.size < 1:
			self._error = "Timesteps not found"
			return

		# Select particles
		# -------------------------------------------------------------------
		# If the selection is a string (containing an operation)
		if sort:
			if type(select) is str:
				# Define a function that finds the next closing character in a string
				def findClosingCharacter(string, character, start=0):
					i = start
					stack = []
					associatedBracket = {")":"(", "]":"[", "}":"{"}
					while i < len(string):
						if string[i] == character and len(stack)==0: return i
						if string[i] in ["(", "[", "{"]:
							stack.append(string[i])
						if string[i] in [")", "]", "}"]:
							if len(stack)==0:
								raise Exception("Error in selector syntax: missing `"+character+"`")
							if stack[-1]!=associatedBracket[string[i]]:
								raise Exception("Error in selector syntax: missing closing parentheses or brackets")
							del stack[-1]
						i+=1
					raise Exception("Error in selector syntax: missing `"+character+"`")
				# Parse the selector
				i = 0
				operation = ""
				seltype = []
				selstr = []
				timeSelector = []
				particleSelector = []
				doubleProps = []
				int16Props = []
				while i < len(select):
					if i+4<len(select) and select[i:i+4] in ["any(","all("]:
						seltype += [select[i:i+4]]
						if seltype[-1] not in ["any(","all("]:
							raise Exception("Error in selector syntax: unknown argument "+seltype[-1][:-1])
						comma = findClosingCharacter(select, ",", i+4)
						parenthesis = findClosingCharacter(select, ")", comma+1)
						timeSelector += [select[i+4:comma]]
						selstr += [select[i:parenthesis]]
						try:
							timeSelector[-1] = "self._alltimesteps["+self._re.sub(r"\bt\b","self._alltimesteps",timeSelector[-1])+"]"
							eval(timeSelector[-1])
						except:
							raise Exception("Error in selector syntax: time selector not understood in "+select[i:i+3]+"()")
						try:
							particleSelector += [select[comma+1:parenthesis]]
							doubleProps += [[]]
							int16Props += [[]]
							for prop in self._h5items.keys():
								(particleSelector[-1], nsubs) = self._re.subn(r"\b"+prop+r"\b", "properties['"+prop+"'][:actual_chunksize]", particleSelector[-1])
								if nsubs > 0:
									if   prop == "q" : int16Props [-1] += [prop]
									else             : doubleProps[-1] += [prop]
						except:
							raise Exception("Error in selector syntax: not understood: "+select[i:parenthesis+1])
						operation += "stack["+str(len(seltype)-1)+"]"
						i = parenthesis+1
					else:
						operation += select[i]
						i+=1
				nOperations = len(seltype)
				# Execute the selector
				if self._verbose: print("Selecting particles ... (this may take a while)")
				if len(operation)==0.:
					self.selectedParticles = self._np.s_[:]
				else:
					# Setup the chunks of particles (if too many particles)
					chunksize = min(chunksize, self.nParticles)
					nchunks = int(self.nParticles / chunksize)
					chunksize = int(self.nParticles / nchunks)
					self.selectedParticles = self._np.array([], dtype=self._np.uint64)
					# Allocate buffers
					properties = {}
					for k in range(nOperations):
						for prop in int16Props[k]:
							if prop not in properties:
								properties[prop] = self._np.empty((chunksize,), dtype=self._np.int16)
						for prop in doubleProps[k]:
							if prop not in properties:
								properties[prop] = self._np.empty((chunksize,), dtype=self._np.double)
					properties["Id"] = self._np.empty((chunksize,), dtype=self._np.uint64)
					selection = self._np.empty((chunksize,), dtype=bool)
					# Loop on chunks
					chunkstop = 0
					for ichunk in range(nchunks):
						chunkstart = chunkstop
						chunkstop  = min(chunkstart + chunksize, self.nParticles)
						actual_chunksize = chunkstop - chunkstart
						# Execute each of the selector items
						stack = []
						for k in range(nOperations):
							if   seltype[k] == "any(": selection.fill(False)
							elif seltype[k] == "all(": selection.fill(True )
							requiredProps = doubleProps[k] + int16Props[k] + ["Id"]
							# Loop times
							times = eval(timeSelector[k])
							for time in times:
								if self._verbose: print("   Selecting block `"+selstr[k]+")`, at time "+str(time))
								# Extract required properties
								it = self._locationForTime[time]
								for prop in requiredProps:
									self._h5items[prop].read_direct(properties[prop], source_sel=self._np.s_[it,chunkstart:chunkstop], dest_sel=self._np.s_[:actual_chunksize])
								# Calculate the selector
								selectionAtTimeT = eval(particleSelector[k]) # array of True or False
								selectionAtTimeT[self._np.isnan(selectionAtTimeT)] = False
								loc = self._np.flatnonzero(properties["Id"][:actual_chunksize]>0) # indices of existing particles
								# Combine wth selection of previous times
								if   seltype[k] == "any(": selection[loc] += selectionAtTimeT[loc]
								elif seltype[k] == "all(": selection[loc] *= selectionAtTimeT[loc]
							stack.append(selection)
						# Merge all stack items according to the operations
						self.selectedParticles = self._np.union1d( self.selectedParticles, eval(operation).nonzero()[0] )
					self.selectedParticles.sort()

			# Otherwise, the selection can be a list of particle IDs
			else:
				try:
					IDs = f["unique_Ids"] # get all available IDs
					self.selectedParticles = self._np.flatnonzero(self._np.in1d(IDs, select)) # find the requested IDs
				except:
					self._error = "Error: argument 'select' must be a string or a list of particle IDs"
					return

			# Remove particles that are not actually tracked during the requested timesteps
			if type(self.selectedParticles) is not slice and len(self.selectedParticles) > 0:
				first_time = self._locationForTime[self._timesteps[ 0]]
				last_time  = self._locationForTime[self._timesteps[-1]]+1
				IDs = self._h5items["Id"][first_time:last_time,self.selectedParticles]
				dead_particles = self._np.flatnonzero(self._np.all( self._np.isnan(IDs) + (IDs==0), axis=0 ))
				self.selectedParticles = self._np.delete( self.selectedParticles, dead_particles )

			# Calculate the number of selected particles
			if type(self.selectedParticles) is slice:
				self.nselectedParticles = self.nParticles
			else:
				self.nselectedParticles = len(self.selectedParticles)
			if self.nselectedParticles == 0:
				self._error = "No particles found"
				return
			if self._verbose: print("Kept "+str(self.nselectedParticles)+" particles")

		# Manage axes
		# -------------------------------------------------------------------
		if type(axes) is not list:
			self._error = "Error: Argument 'axes' must be a list"
			return
		# if axes provided, verify them
		if len(axes)>0:
			self.axes = axes
			for axis in axes:
				if axis not in self.available_properties:
					self._error += "Error: Argument 'axes' has item '"+str(axis)+"' unknown.\n"
					self._error += "       Available axes are: "+(", ".join(sorted(self.available_properties)))
					return
		# otherwise use default
		else:
			self.axes = self.available_properties

		# Then figure out axis units
		if self._sort:
			self._type = self.axes
			for axis in self.axes:
				axisunits = ""
				if axis == "Id":
					self._centers.append( [0, 281474976710655] )
				elif axis in ["x" , "y" , "z" ]:
					axisunits = "L_r"
					self._centers.append( [0., self.namelist.Main.grid_length[{"x":0,"y":1,"z":2}[axis]]] )
				elif axis in ["px", "py", "pz"]:
					axisunits = "P_r"
					self._centers.append( [-1., 1.] )
				elif axis == "w":
					axisunits = "N_r"
					self._centers.append( [0., 1.] )
				elif axis == "q":
					axisunits = "Q_r"
					self._centers.append( [-10., 10.] )
				elif axis == "chi":
					axisunits = "1"
					self._centers.append( [0., 2.] )
				elif axis[0] == "E":
					axisunits = "E_r"
					self._centers.append( [-1., 1.] )
				elif axis[0] == "B":
					axisunits = "B_r"
					self._centers.append( [-1., 1.] )
				self._log.append( False )
				self._label.append( axis )
				self._units.append( axisunits )
			self._title = "Track particles '"+species+"'"
			self._shape = [0]*len(self.axes)

		# Hack to work with 1 axis
		if len(axes)==1: self._vunits = self._units[0]
		else: self._vunits = ""

		# Set the directory in case of exporting
		self._exportPrefix = "TrackParticles_"+self.species+"_"+"".join(self.axes)
		self._exportDir = self._setExportDir(self._exportPrefix)

		self._rawData = None

		# Finish constructor
		self.length = length or self._timesteps[-1]
		self.valid = True
		return kwargs

	# Method to get info
	def _info(self):
		info = "Track particles: species '"+self.species+"'"
		if self._sort:
			info += " containing "+str(self.nParticles)+" particles"
			if self.nselectedParticles != self.nParticles:
				info += "\n                with selection of "+str(self.nselectedParticles)+" particles"
		return info

	# get all available tracked species
	def getTrackSpecies(self):
		for path in self._results_path:
			files = self._glob(path+self._os.sep+"TrackParticles*.h5")
			species_here = [self._re.search("_(.+).h5",self._os.path.basename(file)).groups()[0] for file in files]
			try   : species = [ s for s in species if s in species_here ]
			except: species = species_here
		return species

	# get all available timesteps
	def getAvailableTimesteps(self):
		return self._alltimesteps

	# Get a list of disordered files
	def _findDisorderedFiles(self):
		disorderedfiles = []
		for path in self._results_path:
			file = path+self._os.sep+"TrackParticlesDisordered_"+self.species+".h5"
			if not self._os.path.isfile(file):
				self._error = "Missing TrackParticles file in directory "+path
				return
			disorderedfiles += [file]
		return disorderedfiles

	# Make the particles ordered by Id in the file, in case they are not
	def _orderFiles( self, filesDisordered, fileOrdered, chunksize ):
		import math
		if self._verbose: print("Ordering particles ... (this could take a while)")
		try:
			properties = {"id":"Id", "position/x":"x", "position/y":"y", "position/z":"z",
			              "momentum/x":"px", "momentum/y":"py", "momentum/z":"pz",
			              "charge":"q", "weight":"w", "chi":"chi",
			              "E/x":"Ex", "E/y":"Ey", "E/z":"Ez",
			              "B/x":"Bx", "B/y":"By", "B/z":"Bz"}
			# Obtain the list of all times in all disordered files
			time_locations = {}
			for fileIndex, fileD in enumerate(filesDisordered):
				f = self._h5py.File(fileD, "r")
				for t in f["data"].keys():
					try   : time_locations[int(t)] = (fileIndex, t)
					except: pass
				f.close()
			times = sorted(time_locations.keys())
			# Open the last file and get the number of particles from each MPI
			last_file_index, tname = time_locations[times[-1]]
			f = self._h5py.File(filesDisordered[last_file_index], "r")
			number_of_particles = (f["data"][tname]["latest_IDs"].value % (2**32)).astype('uint32')
			if self._verbose: print("Number of particles: "+str(number_of_particles.sum()))
			# Calculate the offset that each MPI needs
			offset = self._np.cumsum(number_of_particles)
			total_number_of_particles = offset[-1]
			offset = self._np.roll(offset, 1)
			offset[0] = 0
			# If ordered file already exists, find out which timestep was done last
			latestOrdered = -1
			if self._os.path.isfile(fileOrdered):
				f0 = self._h5py.File(fileOrdered, "r+")
				try:    latestOrdered = f0.attrs["latestOrdered"]
				except: pass
			# otherwise, make new (ordered) file
			else:
				f0 = self._h5py.File(fileOrdered, "w")
			# Make datasets if not existing already
			for k, name in properties.items():
				try   : f0.create_dataset(name, (len(times), total_number_of_particles), f["data"][tname]["particles"][self.species][k].dtype, fillvalue=(0 if name=="Id" else self._np.nan))
				except: pass
			f.close()
			# Loop times and fill arrays
			for it, t in enumerate(times):

				# Skip previously-ordered times
				if it<=latestOrdered: continue

				if self._verbose: print("    Ordering @ timestep = "+str(t))
				file_index, tname = time_locations[t]
				f = self._h5py.File(filesDisordered[file_index], "r")
				group = f["data"][tname]["particles"][self.species]
				nparticles = group["id"].size
				if nparticles == 0: continue

				# If not too many particles, sort all at once
				if nparticles < chunksize:
					# Get the Ids and find where they should be stored in the final file
					locs = (
						group["id"].value.astype("uint32") # takes the second hald of id (meaning particle number)
						+ offset[ (group["id"].value>>32).astype("uint32") & 16777215 ]# 0b111111111111111111111111
						-1
					)
					# Loop datasets and order them
					for k, name in properties.items():
						if k not in group: continue
						disordered = group[k].value
						ordered = self._np.zeros((total_number_of_particles, ), dtype=disordered.dtype)
						ordered[locs] = disordered
						f0[name].write_direct(ordered, dest_sel=self._np.s_[it,:])

				# If too many particles, sort by chunks
				else:
					nchunks = int(float(nparticles)/(chunksize+1) + 1)
					adjustedchunksize = int(math.ceil(float(nparticles)/nchunks))
					ID = self._np.empty((adjustedchunksize,), dtype=self._np.uint64)
					data_double = self._np.empty((adjustedchunksize,))
					data_int16  = self._np.empty((adjustedchunksize,), dtype=self._np.int16)
					# Loop chunks
					for ichunk in range(nchunks):
						first = ichunk * adjustedchunksize
						last  = min( first + adjustedchunksize, nparticles )
						npart = last-first
						# Obtain IDs and find their sorting indices
						group["id"].read_direct( ID, source_sel=self._np.s_[first:last], dest_sel=self._np.s_[:npart] )
						sort = self._np.argsort(ID[:npart])
						ID[:npart] = ID[sort]
						# Find consecutive-ID batches
						batchsize = self._np.diff(self._np.concatenate(([0],1+self._np.flatnonzero(self._np.diff(ID[:npart])-1), [npart])))
						# Loop datasets
						for k, name in properties.items():
							if k not in group: continue
							# Get the data for this chunk and sort by ID
							if k == "charge": data = data_int16
							else:             data = data_double
							group[k].read_direct( data, source_sel=self._np.s_[first:last], dest_sel=self._np.s_[:npart] )
							data[:npart] = data[sort]
							# Loop by batch inside this chunk and store at the right place
							stop = 0
							for ibatch in range(len(batchsize)):
								bs = int(batchsize[ibatch])
								start = stop
								stop = start + bs
								start_in_file = int(
									(ID[start].astype("uint32"))
									+ offset[ (int(ID[start])>>32).astype("uint32") & 16777215 ]
									-1
								)
								stop_in_file = start_in_file + bs
								f0[name].write_direct( data, source_sel=self._np.s_[start:stop], dest_sel=self._np.s_[it, start_in_file:stop_in_file] )

				# Indicate that this iteration was succesfully ordered
				f0.attrs["latestOrdered"] = it
				f0.flush()
				f.close()
			if self._verbose: print("    Finalizing the ordering process")
			# Create the "Times" dataset
			f0.create_dataset("Times", data=times)
			# Create the "unique_Ids" dataset
			limitedchunksize = int(chunksize / len(times))
			if total_number_of_particles < limitedchunksize:
				f0.create_dataset("unique_Ids", data=self._np.max(f0["Id"], axis=0))
			else:
				f0.create_dataset("unique_Ids", (total_number_of_particles,), f0["Id"].dtype)
				nchunks = int(float(total_number_of_particles)/(limitedchunksize+1) + 1)
				limitedchunksize = int(math.ceil(float(total_number_of_particles)/nchunks))
				ID = self._np.empty((len(times),limitedchunksize), dtype=self._np.uint64)
				for ichunk in range(nchunks):
					first = ichunk * limitedchunksize
					last  = int(min( first + limitedchunksize, total_number_of_particles ))
					npart = last-first
					f0["Id"].read_direct( ID, source_sel=self._np.s_[:, first:last], dest_sel=self._np.s_[:,:npart] )
					f0["unique_Ids"].write_direct( self._np.max(ID[:,:npart], axis=0), source_sel=self._np.s_[:npart], dest_sel=self._np.s_[first:last] )
			# Indicate that the ordering is finished
			f0.attrs["finished_ordering"] = True
			# Close file
			f0.close()
		except:
			print("Error in the ordering of the tracked particles")
			raise
		if self._verbose: print("Ordering succeeded")

	# Method to generate the raw data (only done once)
	def _generateRawData(self, times=None):
		if not self._validate(): return
		self._prepare1() # prepare the vfactor

		if self._sort:
			if self._rawData is None:
				self._rawData = {}

				if self._verbose: print("Preparing data ...")
				# create dictionary with info on the axes
				ntimes = len(self._timesteps)
				for axis in self.axes:
					if axis == "Id":
						self._rawData[axis] = self._np.empty((ntimes, self.nselectedParticles), dtype=(self._np.uint64))
						self._rawData[axis].fill(0)
					elif axis == "q":
						self._rawData[axis] = self._np.empty((ntimes, self.nselectedParticles), dtype=(self._np.int16 ))
						self._rawData[axis].fill(0)
					else:
						self._rawData[axis] = self._np.empty((ntimes, self.nselectedParticles), dtype=(self._np.double))
						self._rawData[axis].fill(self._np.nan)
				if self._verbose: print("Loading data ...")
				# loop times and fill up the data
				ID = self._np.zeros((self.nselectedParticles,), dtype=self._np.uint64)
				data_double = self._np.zeros((self.nselectedParticles,), dtype=self._np.double)
				data_int16  = self._np.zeros((self.nselectedParticles,), dtype=self._np.int16 )
				for it, time in enumerate(self._timesteps):
					if self._verbose: print("     iteration "+str(it+1)+"/"+str(ntimes)+"  (timestep "+str(time)+")")
					timeIndex = self._locationForTime[time]
					self._h5items["Id"].read_direct(ID, source_sel=self._np.s_[timeIndex,self.selectedParticles]) # read the particle Ids
					deadParticles = (ID==0).nonzero()
					for axis in self.axes:
						if axis == "Id":
							self._rawData[axis][it, :] = ID.squeeze()
						elif axis == "q":
							self._h5items[axis].read_direct(data_int16, source_sel=self._np.s_[timeIndex,self.selectedParticles])
							self._rawData[axis][it, :] = data_int16.squeeze()
						else:
							self._h5items[axis].read_direct(data_double, source_sel=self._np.s_[timeIndex,self.selectedParticles])
							data_double[deadParticles]=self._np.nan
							self._rawData[axis][it, :] = data_double.squeeze()
				if self._verbose: print("Process broken lines ...")
				# Add the lineBreaks array which indicates where lines are broken (e.g. loop around the box)
				self._rawData['brokenLine'] = self._np.zeros((self.nselectedParticles,), dtype=bool)
				self._rawData['lineBreaks'] = {}
				if self._timesteps.size > 1:
					dt = self._np.diff(self._timesteps)*self.timestep
					for axis in ["x","y","z"]:
						if axis in self.axes:
							dudt = self._np.diff(self._rawData[axis],axis=0)
							for i in range(dudt.shape[1]): dudt[:,i] /= dt
							dudt[~self._np.isnan(dudt)] = 0. # NaNs already break lines
							# Line is broken if velocity > c
							self._rawData['brokenLine'] += self._np.abs(dudt).max(axis=0) > 1.
							broken_particles = self._np.flatnonzero(self._rawData['brokenLine'])
							for broken_particle in broken_particles:
								broken_times = list(self._np.flatnonzero(self._np.abs(dudt[:,broken_particle]) > 1.)+1)
								if broken_particle in self._rawData['lineBreaks'].keys():
									self._rawData['lineBreaks'][broken_particle] += broken_times
								else:
									self._rawData['lineBreaks'][broken_particle] = broken_times
				# Add the times array
				self._rawData["times"] = self._timesteps
				if self._verbose: print("... done")

		# If not sorted, get different kind of data
		else:
			if self._rawData is None:
				self._rawData = {}

			if self._verbose: print("Loading data ...")
			properties = {"Id":"id", "x":"position/x", "y":"position/y", "z":"position/z",
			              "px":"momentum/x", "py":"momentum/y", "pz":"momentum/z",
			              "q":"charge", "w":"weight","chi":"chi",
			              "Ex":"E/x", "Ey":"E/y", "Ez":"E/z",
			              "Bx":"B/x", "By":"B/y", "Bz":"B/z"}
			if times is None: times = self._timesteps
			for time in times:
				if time in self._rawData: continue
				[f, timeIndex] = self._locationForTime[time]
				group = f["data/"+"%010i"%time+"/particles/"+self.species]
				self._rawData[time] = {}
				for axis in self.axes:
					self._rawData[time][axis] = group[properties[axis]].value

			if self._verbose: print("... done")

	# We override the get and getData methods
	def getData(self, timestep=None):
		if not self._validate(): return
		self._prepare1() # prepare the vfactor

		if timestep is None:
			ts = self._timesteps
		elif timestep not in self._timesteps:
			print("ERROR: timestep "+str(timestep)+" not available")
			return {}
		else:
			ts = [timestep]
			indexOfRequestedTime = self._np.where(self._timesteps==timestep)

		if len(ts)==1 and not self._sort:
			self._generateRawData(ts)
		else:
			self._generateRawData()

		data = {}
		data.update({ "times":ts })

		if self._sort:
			for axis in self.axes:
				if timestep is None:
					data[axis] = self._rawData[axis]
				else:
					data[axis] = self._rawData[axis][indexOfRequestedTime]
				if axis not in ["Id", "q"]: data[axis] *= self._vfactor
		else:
			for t in ts:
				data[t] = {}
				for axis in self.axes:
					data[t][axis] = self._rawData[t][axis]
					if axis not in ["Id", "q"]: data[t][axis] *= self._vfactor

		return data

	def get(self):
		return self.getData()

	# Iterator on UNSORTED particles for a given timestep
	def iterParticles(self, timestep, chunksize=1):
		if not self._validate(): return
		self._prepare1() # prepare the vfactor

		if timestep not in self._timesteps:
			print("ERROR: timestep "+str(timestep)+" not available")
			return

		properties = {"Id":"id", "x":"position/x", "y":"position/y", "z":"position/z",
		              "px":"momentum/x", "py":"momentum/y", "pz":"momentum/z",
		              "q":"charge", "w":"weight","chi":"chi",
		              "Ex":"E/x", "Ey":"E/y", "Ez":"E/z",
		              "Bx":"B/x", "By":"B/y", "Bz":"B/z"}

		disorderedfiles = self._findDisorderedFiles()
		for file in disorderedfiles:
			f = self._h5py.File(file)
			# This is the timestep for which we want to produce an iterator
			group = f["data/"+("%010d"%timestep)+"/particles/"+self.species]
			npart = group["id"].size
			ID          = self._np.empty((chunksize,), dtype=self._np.uint64)
			data_double = self._np.empty((chunksize,), dtype=self._np.double)
			data_int16  = self._np.empty((chunksize,), dtype=self._np.int16 )
			for chunkstart in range(0, npart, chunksize):
				chunkend = chunkstart + chunksize
				if chunkend > npart:
					chunkend = npart
					ID          = self._np.empty((chunkend-chunkstart,), dtype=self._np.uint64)
					data_double = self._np.empty((chunkend-chunkstart,), dtype=self._np.double)
					data_int16  = self._np.empty((chunkend-chunkstart,), dtype=self._np.int16 )
				data = {}
				for axis in self.axes:
					if axis == "Id":
						group[properties[axis]].read_direct(ID, source_sel=self._np.s_[chunkstart:chunkend])
						data[axis] = ID.copy()
					elif axis == "q":
						group[properties[axis]].read_direct(data_int16, source_sel=self._np.s_[chunkstart:chunkend])
						data[axis] = data_int16.copy()
					else:
						group[properties[axis]].read_direct(data_double, source_sel=self._np.s_[chunkstart:chunkend])
						data[axis] = data_double.copy()
				yield data
			return

	# We override _prepare3
	def _prepare3(self):
		if not self._sort:
			print("Cannot plot non-sorted data")
			return False
		if self._tmpdata is None:
			A = self.getData()
			self._tmpdata = []
			for axis in self.axes: self._tmpdata.append( A[axis] )
		return True


	# We override the plotting methods
	def _animateOnAxes_0D(self, ax, t):
		pass

	def _animateOnAxes_1D(self, ax, t):
		timeSelection = (self._timesteps<=t)*(self._timesteps>=t-self.length)
		times = self._timesteps[timeSelection]
		A     = self._tmpdata[0][timeSelection,:]
		if times.size == 1:
			times = self._np.double([times, times]).squeeze()
			A = self._np.double([A, A]).squeeze()
		ax.plot(self._tfactor*times, self._vfactor*A, **self.options.plot)
		ax.set_xlabel(self._tlabel)
		ax.set_ylabel(self.axes[0]+" ("+self.units.vname+")")
		self._setLimits(ax, xmax=self._tfactor*self._timesteps[-1], ymin=self.options.vmin, ymax=self.options.vmax)
		self._setSomeOptions(ax)
		ax.set_title(self._title) # override title
		return 1

	def _animateOnAxes_2D(self, ax, t):
		tmin = t-self.length
		tmax = t
		timeSelection = (self._timesteps<=tmax)*(self._timesteps>=tmin)
		selected_times = self._np.flatnonzero(timeSelection)
		itmin = selected_times[0]
		itmax = selected_times[-1]
		# Plot first the non-broken lines
		x = self._tmpdata[0][timeSelection,:][:,~self._rawData["brokenLine"]]
		y = self._tmpdata[1][timeSelection,:][:,~self._rawData["brokenLine"]]
		ax.plot(self._xfactor*x, self._yfactor*y, **self.options.plot)
		# Then plot the broken lines
		ax.hold("on")
		for line, breaks in self._rawData['lineBreaks'].items():
			x = self._tmpdata[0][:, line]
			y = self._tmpdata[1][:, line]
			prevline = None
			for ibrk in range(len(breaks)):
				if breaks[ibrk] <= itmin: continue
				iti = itmin
				if ibrk>0: iti = max(itmin, breaks[ibrk-1])
				itf = min( itmax, breaks[ibrk] )
				if prevline:
					ax.plot(self._xfactor*x[iti:itf], self._yfactor*y[iti:itf], color=prevline.get_color(), **self.options.plot)
				else:
					prevline, = ax.plot(self._xfactor*x[iti:itf], self._yfactor*y[iti:itf], **self.options.plot)
				if breaks[ibrk] > itmax: break
		ax.hold("off")
		# Add labels and options
		ax.set_xlabel(self._xlabel)
		ax.set_ylabel(self._ylabel)
		self._setLimits(ax, xmin=self.options.xmin, xmax=self.options.xmax, ymin=self.options.ymin, ymax=self.options.ymax)
		self._setSomeOptions(ax)
		return 1

	# Convert data to VTK format
	def toVTK(self, numberOfPieces=1, rendering="trajectory"):
		if not self._validate(): return

		if not self._sort:
			print("Cannot export non-sorted data")
			return

		if self._ndim!=3:
			print ("Cannot export tracked particles of a "+str(self._ndim)+"D simulation to VTK")
			return

		if rendering not in ["trajectory","cloud"]:
			print ("Rendering of type {} is not valid.".format(rendering))
			return

		self._mkdir(self._exportDir)
		fileprefix = self._exportDir + self._exportPrefix

		ntimes = len(self._timesteps)

		# Creation of a customed vtk object
		vtk = VTKfile()

		# If 3D simulation, then do a 3D plot
		if self._ndim == 3:
			if "x" not in self.axes or "y" not in self.axes or "z" not in self.axes:
				print("Error exporting tracked particles to VTK: axes 'x', 'y' and 'z' are required")
				return

			if (ntimes == 1)or(rendering == "cloud"):

				data = self.getData()
				pcoords = self._np.stack((data["x"],data["y"],data["z"]))
				nd, nt, npoints = pcoords.shape

				for istep,step in enumerate(self._timesteps):
					pcoords_step = self._np.stack((pcoords[0][istep],pcoords[1][istep],pcoords[2][istep])).transpose()
					pcoords_step = self._np.ascontiguousarray(pcoords_step, dtype='float32')

					# Convert pcoords that is a numpy array into vtkFloatArray
					pcoords_step = vtk.Array(pcoords_step, "")

					# List of scalar arrays
					attributes = []
					for ax in self.axes:
						if ax!="x" and  ax!="y" and  ax!="z":
							attributes += [vtk.Array(self._np.ascontiguousarray(data[ax][istep].flatten(),'float32'),ax)]

					vtk.WriteCloud(pcoords_step, attributes, fileprefix+"_{:06d}.vtk".format(step))
					print("Exportation of {}_{:06d}.vtk".format(fileprefix,step))

				print("Successfully exported tracked particles to VTK, folder='"+self._exportDir)

			elif (rendering == "trajectory"):

				data = self.getData()
				pcoords = self._np.stack((data["x"],data["y"],data["z"])).transpose()
				npoints, nt, nd = pcoords.shape

				pcoords = self._np.reshape(pcoords, (npoints*nt, nd))
				pcoords = self._np.ascontiguousarray(pcoords, dtype='float32')

				# Convert pcoords that is a numpy array into vtkFloatArray
				pcoords = vtk.Array(pcoords, "")

				# Segments between points to describe the trajectories
				connectivity = self._np.ascontiguousarray([[nt]+[nt*i+j for j in range(nt)] for i in range(npoints)])

				# List of scalar arrays
				attributes = []
				for ax in self.axes:
					if ax!="x" and  ax!="y" and  ax!="z":
						attributes += [vtk.Array(self._np.ascontiguousarray(data[ax].flatten(),'float32'),ax)]

				vtk.WriteLines(pcoords, connectivity, attributes, fileprefix+".vtk")
				print("Successfully exported tracked particles to VTK, folder='"+self._exportDir)
