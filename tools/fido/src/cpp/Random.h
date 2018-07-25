#ifndef _Random_H
#define _Random_H

#include <iostream>
#include <math.h>

#include "Array.h"
#include "Numerical.h"

using namespace std;

class Random
{
 public:
  static double uniform(double a, double b);
  static int inRange(int a, int b);

  static double standardNormal();
  static double normal(double mean, double var);

  static void fillRandomUniform(Array<double> & lhs, double low, double high);

  class SamplingException :public exception {
   virtual const char* what() const throw()
   {
    return "random: sampling exception";
   }
  };
private:
  static Numerical samplingChecker;
};

#endif

