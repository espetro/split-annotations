/**
 * Demo for DAWN Retreat 2019.
 *
 * Let's add vectors really quickly using Mozart!
 *
 */

#include <stdlib.h>
#include <stdio.h>
#include <sys/time.h>

#include "mkl_vml_functions.h"
#include "mkl.h"

// Wrapper library
#include "generated/generated.h"
// Allocation functions
#include <composer.h>

// Adds a vector with itself many times.
void add_many_times(int times,
    double *vector,
    MKL_INT length) {
  for (int i = 0; i < times; ++i) {
    // MKL's add function.
    // Performs elementwise vector[i] = vector[i] + vector[i].
    c_vdAdd(length, vector, vector, vector);
  }
}

// ------------ Driver -----------------

int main(int argc, char **argv) {
    const size_t length = 500000000;
    double *data = (double *)mozart_malloc(sizeof(double) * length);
    for (int i = 0; i < length; i++) {
        data[i] = i;
    }

    struct timeval start, end, diff;
    gettimeofday(&start, NULL);
    add_many_times(10, data, length);

    double first = data[12];
    printf("First value: %f\n", first);

    gettimeofday(&end, NULL);
    timersub(&end, &start, &diff);
    double runtime = (double)diff.tv_sec + ((double)diff.tv_usec / 1000000.0);
    printf("Runtime: %f seconds\n", runtime);
}

