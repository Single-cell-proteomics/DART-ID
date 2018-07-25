#ifndef _ProteinIdentifier_H
#define _ProteinIdentifier_H

#include "StringTable.h"
#include "Array.h"
#include "Set.h"
#include "Matrix.h"
#include "Random.h"
#include "Model.h"

using namespace std;

class ProteinIdentifier
{
public:
  ProteinIdentifier();
  virtual ~ProteinIdentifier() {}

  friend istream & operator >>(istream & is, ProteinIdentifier & pi)
  {
    pi.read(is);
    return is;
  }

  virtual void printProteinWeights() const = 0;

  class FormatException : public exception {
   virtual const char* what() const throw()
   {
    return "protein identifier: format exception";
   }
  };

  // note: this should be private later
  double ProteinThreshold, PeptideThreshold;
protected:

  virtual void read(istream & is) = 0;

  static Array<double> PeptideProphetPriorAtChargeState;
};

#endif

